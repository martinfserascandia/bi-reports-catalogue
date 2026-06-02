"""fabric_security_audit.py

Security audit for all Fabric reports in the inventory CSV.
For each report, collects:
  - Workspace membership and roles
  - Report-level user permissions
  - Linked semantic model user permissions
  - Upstream lakehouse identification (via Scanner API lineage — Direct Lake)
  - Lakehouse workspace membership

Strategy:
  1. Extract all unique workspace IDs from the CSV
  2. Run Power BI Admin Scanner API for all workspaces at once
     (lineage=true returns Direct Lake → Lakehouse upstream connections)
  3. Fetch Fabric workspace items to identify lakehouses
  4. Fall back to individual admin API calls for anything the Scanner missed

Prerequisites:
  - Azure CLI logged in: az login --tenant 1dc7fe1c-3fd1-428f-b745-de881b406952
  - Caller needs Power BI Admin or Fabric Admin role to use admin/* endpoints
    (non-admin fallbacks are tried automatically but return limited data)

Run:
  python fabric_security_audit.py

Outputs:
  security_audit_YYYYMMDD_HHMMSS.csv
  security_audit.log
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from azure.identity import AzureCliCredential, ClientSecretCredential, DefaultAzureCredential

# ── Constants ─────────────────────────────────────────────────────────────────
TENANT_ID = "1dc7fe1c-3fd1-428f-b745-de881b406952"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
CSV_INPUT = "fabric_reports_20260504_140808.csv"
SCANNER_BATCH_SIZE = 100  # max workspaces per Scanner API request

OUTPUT_CSV = f"security_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
LOG_FILE = "security_audit.log"

# Local cache files — reused across runs to avoid hitting the 200 req/hr quota.
# Delete these files to force a fresh fetch (e.g. after workspace changes).
CACHE_SCANNER = Path("cache_scanner.json")
CACHE_WS_ITEMS = Path("cache_ws_items.json")
CACHE_MAX_AGE_HOURS = 24

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("security_audit")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
_sh.setLevel(logging.INFO)
_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setFormatter(_fmt)
logger.handlers.clear()
logger.addHandler(_sh)
logger.addHandler(_fh)


# ── Cache helpers ─────────────────────────────────────────────────────────────
def _cache_load(path: Path) -> dict | None:
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > CACHE_MAX_AGE_HOURS:
        logger.info("Cache %s is %.1f hours old — ignoring", path.name, age_hours)
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    logger.info("Loaded cache %s (%.1f hours old)", path.name, age_hours)
    return data


def _cache_save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved cache %s", path.name)


# ── Auth ──────────────────────────────────────────────────────────────────────
def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_credential():
    mode = os.getenv("FABRIC_AUTH_MODE", "azure_cli").lower()
    tenant = os.getenv("AZURE_TENANT_ID", TENANT_ID).strip()
    if mode == "service_principal":
        return ClientSecretCredential(
            tenant_id=tenant,
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
        )
    if mode == "default":
        return DefaultAzureCredential()
    return AzureCliCredential(tenant_id=tenant)


_token_cache: dict[str, tuple[str, float]] = {}


def get_headers(credential, scope: str) -> dict[str, str]:
    cached = _token_cache.get(scope)
    if cached and cached[1] > time.time() + 120:
        return {"Authorization": f"Bearer {cached[0]}", "Content-Type": "application/json"}
    tok = credential.get_token(scope)
    _token_cache[scope] = (tok.token, tok.expires_on)
    return {"Authorization": f"Bearer {tok.token}", "Content-Type": "application/json"}


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _get(url: str, headers: dict, params: dict | None = None) -> dict | None:
    for _ in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            logger.warning("GET %s → %s", url, e)
            return None
        if resp.status_code == 429:
            delay = int(resp.headers.get("Retry-After", 30))
            logger.warning("Rate limited — waiting %ds", delay)
            time.sleep(delay)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            logger.warning("GET %s → 403 Forbidden (missing admin role?)", url)
        else:
            logger.debug("GET %s → %d: %s", url, resp.status_code, resp.text[:300])
        return None
    return None


def _post(url: str, headers: dict, body: dict, params: dict | None = None) -> dict | None:
    for _ in range(3):
        try:
            resp = requests.post(url, headers=headers, json=body, params=params, timeout=60)
        except requests.RequestException as e:
            logger.warning("POST %s → %s", url, e)
            return None
        if resp.status_code == 429:
            delay = int(resp.headers.get("Retry-After", 30))
            logger.warning("Rate limited — waiting %ds", delay)
            time.sleep(delay)
            continue
        if resp.status_code in (200, 202):
            return resp.json()
        logger.debug("POST %s → %d: %s", url, resp.status_code, resp.text[:300])
        return None
    return None


# ── Scanner API ───────────────────────────────────────────────────────────────
def run_scanner(workspace_ids: list[str], credential) -> dict[str, dict]:
    """
    Run the Power BI Admin Scanner API for a batch of workspace IDs.
    Requires Power BI/Fabric Admin role.
    Returns dict keyed by workspace_id with full workspace data including lineage.
    """
    pbi_h = get_headers(credential, PBI_SCOPE)
    params = {
        "lineage": "true",
        "datasourceDetails": "true",
        "artifactUsers": "true",
    }
    body = {"workspaces": workspace_ids}
    logger.info("Scanner: submitting %d workspace(s)…", len(workspace_ids))

    scan_resp = _post(f"{PBI_BASE}/admin/workspaces/getInfo", pbi_h, body, params=params)
    if not scan_resp:
        logger.warning("Scanner API unavailable — will use per-item fallback APIs")
        return {}

    scan_id = scan_resp.get("id")
    logger.info("Scanner scan started: id=%s status=%s", scan_id, scan_resp.get("status"))

    # Poll until complete (max ~2.5 min)
    for attempt in range(30):
        time.sleep(5)
        status = _get(
            f"{PBI_BASE}/admin/workspaces/scanStatus/{scan_id}",
            get_headers(credential, PBI_SCOPE),
        )
        if not status:
            continue
        state = status.get("status", "")
        logger.info("  poll %02d/30 — %s", attempt + 1, state)
        if state == "Succeeded":
            break
        if state == "Failed":
            logger.error("Scanner scan failed: %s", status)
            return {}
    else:
        logger.warning("Scanner scan timed out — falling back to per-item APIs")
        return {}

    result = _get(
        f"{PBI_BASE}/admin/workspaces/scanResult/{scan_id}",
        get_headers(credential, PBI_SCOPE),
    )
    if not result:
        return {}

    workspaces = result.get("workspaces", [])
    logger.info("Scanner returned data for %d workspace(s)", len(workspaces))
    return {ws["id"]: ws for ws in workspaces}


# ── Fallback individual APIs ──────────────────────────────────────────────────
def get_workspace_users_api(workspace_id: str, credential) -> list[dict]:
    pbi_h = get_headers(credential, PBI_SCOPE)
    data = _get(f"{PBI_BASE}/admin/groups/{workspace_id}/users", pbi_h)
    if data:
        return data.get("value", [])
    # Non-admin fallback (only returns members visible to the caller)
    data = _get(f"{PBI_BASE}/groups/{workspace_id}/users", pbi_h)
    if data:
        return data.get("value", [])
    logger.warning("Could not fetch users for workspace %s — check admin role or workspace access", workspace_id)
    return []


def get_report_users_api(report_id: str, credential) -> list[dict]:
    pbi_h = get_headers(credential, PBI_SCOPE)
    data = _get(f"{PBI_BASE}/admin/reports/{report_id}/users", pbi_h)
    return data.get("value", []) if data else []


def get_dataset_users_api(dataset_id: str, credential) -> list[dict]:
    pbi_h = get_headers(credential, PBI_SCOPE)
    data = _get(f"{PBI_BASE}/admin/datasets/{dataset_id}/users", pbi_h)
    return data.get("value", []) if data else []


def get_report_dataset_id(workspace_id: str, report_id: str, credential) -> str:
    pbi_h = get_headers(credential, PBI_SCOPE)
    data = _get(f"{PBI_BASE}/groups/{workspace_id}/reports/{report_id}", pbi_h)
    return data.get("datasetId", "") if data else ""


def get_workspace_items_api(workspace_id: str, credential) -> list[dict]:
    fab_h = get_headers(credential, FABRIC_SCOPE)
    data = _get(f"{FABRIC_BASE}/workspaces/{workspace_id}/items", fab_h)
    return data.get("value", []) if data else []


def get_lakehouse_item_access(lakehouse_id: str, workspace_id: str, credential) -> list[dict]:
    """
    Get item-level access entries for a specific lakehouse via the Fabric Admin API.
    Endpoint: GET /v1/admin/workspaces/{workspaceId}/items/{itemId}/users
    Handles pagination automatically.

    Permission types in itemAccessDetails.type:
      Read    — can see the item, view reports built on it
      ReadAll — SQL analytics endpoint access; can query the Direct Lake model data
      Write   — can write data to the lakehouse
      Reshare — can share the item with others
    """
    fab_h = get_headers(credential, FABRIC_SCOPE)
    results: list[dict] = []
    url: str | None = f"{FABRIC_BASE}/admin/workspaces/{workspace_id}/items/{lakehouse_id}/users"
    while url:
        data = _get(url, fab_h)
        if not data:
            break
        # Log the raw response keys on first page to diagnose field naming
        if not results:
            logger.debug("  item-access raw keys for %s: %s", lakehouse_id, list(data.keys()))
        # Fabric API may use "accessEntities" or "value" depending on endpoint version
        entries = data.get("accessEntities") or data.get("value") or []
        results.extend(entries)
        url = data.get("continuationUri") or data.get("continuationToken") or data.get("@odata.nextLink")
    return results


# ── Formatters ────────────────────────────────────────────────────────────────
_ROLE_FIELDS = ("groupUserAccessRight", "reportUserAccessRight", "datasetUserAccessRight", "role")


def format_users(users: list[dict]) -> str:
    parts = []
    for u in users:
        email = u.get("emailAddress") or u.get("displayName") or u.get("identifier", "?")
        role = next((u[f] for f in _ROLE_FIELDS if f in u), "")
        ptype = u.get("principalType", "User")
        tag = f"[{ptype}] " if ptype != "User" else ""
        parts.append(f"{tag}{email} ({role})")
    return "; ".join(parts)


def format_item_access(entries: list[dict], access_type_filter: str | None = None) -> str:
    """
    Format Fabric item-level access entries.
    Pass access_type_filter="ReadAll" to show only SQL analytics endpoint users.
    """
    parts = []
    for e in entries:
        # The permission type lives in itemAccessDetails.type (Fabric API format)
        access_type = (
            e.get("itemAccessDetails", {}).get("type", "")
            or e.get("accessDetails", {}).get("type", "")
        )
        if access_type_filter and access_type != access_type_filter:
            continue
        email = e.get("email") or e.get("displayName") or e.get("id", "?")
        ptype = e.get("type") or e.get("principalType", "User")
        tag = f"[{ptype}] " if ptype != "User" else ""
        parts.append(f"{tag}{email} ({access_type})")
    return "; ".join(parts)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    _load_env(Path(".env"))
    if not os.getenv("AZURE_CONFIG_DIR"):
        local_az = Path.cwd() / ".az-fabric"
        if local_az.exists():
            os.environ["AZURE_CONFIG_DIR"] = str(local_az)

    credential = build_credential()

    # Validate auth early
    try:
        tok = credential.get_token(PBI_SCOPE)
        logger.info("Auth OK — token expires %s", tok.expires_on)
    except Exception as ex:
        logger.error("Auth failed: %s", ex)
        logger.error("Run: az login --tenant %s", TENANT_ID)
        return 1

    # Load CSV
    csv_path = Path(CSV_INPUT)
    if not csv_path.exists():
        logger.error("CSV not found: %s", csv_path.resolve())
        return 1

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Report ID", "").strip()]
    logger.info("Loaded %d reports from %s", len(rows), CSV_INPUT)

    def extract_ws_id(url: str) -> str | None:
        m = re.search(r"/groups/([0-9a-f-]{36})/", url, re.I)
        return m.group(1) if m else None

    unique_ws_ids = sorted({
        ws
        for row in rows
        if (ws := extract_ws_id(row.get("Report URL", "")))
    })
    logger.info("Unique workspace IDs: %d", len(unique_ws_ids))

    # ── Step 1: Scanner API batch scan ────────────────────────────────────────
    # Cache avoids re-scanning every run (quota: ~200 admin API calls/hour).
    # Delete cache_scanner.json to force a fresh scan.
    scanner_data: dict[str, dict] = {}
    cached_scanner = _cache_load(CACHE_SCANNER)
    if cached_scanner is not None:
        scanner_data = cached_scanner
        logger.info("Scanner: using cached data for %d workspace(s)", len(scanner_data))
    else:
        for i in range(0, len(unique_ws_ids), SCANNER_BATCH_SIZE):
            batch = unique_ws_ids[i : i + SCANNER_BATCH_SIZE]
            scanner_data.update(run_scanner(batch, credential))

    # Index scanner results for fast lookup
    scanner_ws_users: dict[str, list[dict]] = {}
    scanner_datasets: dict[str, dict] = {}
    scanner_reports: dict[str, dict] = {}

    for ws_id, ws_data in scanner_data.items():
        scanner_ws_users[ws_id] = ws_data.get("users", [])
        for ds in ws_data.get("datasets", []):
            ds["_workspaceId"] = ws_id
            scanner_datasets[ds["id"]] = ds
        for rpt in ws_data.get("reports", []):
            rpt["_workspaceId"] = ws_id
            scanner_reports[rpt["id"]] = rpt

    # ── Step 1b: Second Scanner pass for upstream lakehouse workspaces ───────────
    # The first pass only covered report workspaces. Direct Lake models reference
    # lakehouses that may live in completely separate workspaces. Identify those
    # workspace IDs from upstreamArtifacts and scan them now so their user lists
    # are populated before we build the audit rows.
    upstream_ws_to_scan: set[str] = set()
    for ws_data in scanner_data.values():
        for ds in ws_data.get("datasets", []):
            for artifact in ds.get("upstreamArtifacts", []):
                if artifact.get("type") in ("Lakehouse", "Warehouse", "SQLEndpoint"):
                    up_ws = artifact.get("workspaceId", "")
                    if up_ws and up_ws not in scanner_data:
                        upstream_ws_to_scan.add(up_ws)

    if upstream_ws_to_scan:
        logger.info("Step 1b: scanning %d upstream lakehouse workspace(s)…", len(upstream_ws_to_scan))
        upstream_list = sorted(upstream_ws_to_scan)
        for i in range(0, len(upstream_list), SCANNER_BATCH_SIZE):
            batch = upstream_list[i : i + SCANNER_BATCH_SIZE]
            additional = run_scanner(batch, credential)
            scanner_data.update(additional)
        # Update indexes with the newly scanned upstream workspaces
        for ws_id, ws_data in scanner_data.items():
            if ws_id not in scanner_ws_users:
                scanner_ws_users[ws_id] = ws_data.get("users", [])
                for ds in ws_data.get("datasets", []):
                    ds["_workspaceId"] = ws_id
                    scanner_datasets[ds["id"]] = ds
                for rpt in ws_data.get("reports", []):
                    rpt["_workspaceId"] = ws_id
                    scanner_reports[rpt["id"]] = rpt
    else:
        logger.info("Step 1b: no additional upstream workspaces found in lineage")

    # Save scanner data to cache (skip if we loaded from cache this run)
    if cached_scanner is None:
        _cache_save(CACHE_SCANNER, scanner_data)

    # Log a summary of what lineage returned — useful for diagnosing empty results
    total_upstream = sum(
        len([a for a in ds.get("upstreamArtifacts", []) if a.get("type") in ("Lakehouse", "Warehouse", "SQLEndpoint")])
        for ws_data in scanner_data.values()
        for ds in ws_data.get("datasets", [])
    )
    logger.info("Total Direct Lake upstream artifacts found across all datasets: %d", total_upstream)

    # ── Step 2: Fabric item list (lakehouse discovery — lazy, on-demand) ────────
    # Only fetch workspace items when Scanner lineage is absent for a workspace.
    # With the tenant setting enabled most workspaces will have lineage, so this
    # typically costs far fewer calls than pre-fetching all 60 workspaces.
    # Cache persists across runs; delete cache_ws_items.json to force a refresh.
    cached_items = _cache_load(CACHE_WS_ITEMS)
    ws_fabric_items: dict[str, list[dict]] = cached_items if cached_items is not None else {}
    if cached_items is not None:
        logger.info("Workspace items: using cached data for %d workspace(s)", len(ws_fabric_items))

    def _ensure_ws_items(wid: str) -> list[dict]:
        if wid not in ws_fabric_items:
            items = get_workspace_items_api(wid, credential)
            ws_fabric_items[wid] = items
            lh_count = sum(1 for it in items if it.get("type") == "Lakehouse")
            if lh_count:
                logger.info("  Workspace %s — %d lakehouse(s) found", wid, lh_count)
        return ws_fabric_items[wid]

    # ── Step 2b: Pre-fetch lakehouse item-level access (deduplicated) ─────────
    # Collect every unique (workspace_id, lakehouse_id) pair from Scanner lineage
    # upfront, fetch each once, then look up in Step 3 — avoids calling the same
    # endpoint N times when many reports share the same lakehouse.
    lh_access_cache: dict[tuple[str, str], list[dict]] = {}
    lh_pairs_from_lineage: set[tuple[str, str]] = set()
    for ws_data in scanner_data.values():
        for ds in ws_data.get("datasets", []):
            for art in ds.get("upstreamArtifacts", []):
                if art.get("type") in ("Lakehouse", "Warehouse", "SQLEndpoint"):
                    lh_ws = art.get("workspaceId", "")
                    lh_id = art.get("artifactId", "")
                    if lh_ws and lh_id:
                        lh_pairs_from_lineage.add((lh_ws, lh_id))

    if lh_pairs_from_lineage:
        logger.info("Pre-fetching item-level access for %d unique lakehouse(s)…", len(lh_pairs_from_lineage))
        for lh_ws, lh_id in sorted(lh_pairs_from_lineage):
            entries = get_lakehouse_item_access(lh_id, lh_ws, credential)
            lh_access_cache[(lh_ws, lh_id)] = entries
            logger.debug("  Lakehouse %s — %d access entries", lh_id, len(entries))

    # ── Step 3: Build audit rows ──────────────────────────────────────────────
    output_rows = []
    ws_users_cache: dict[str, list[dict]] = {}

    # counters for summary
    cnt_lh_found = 0
    cnt_lh_not_found = 0
    cnt_personal = 0

    for i, row in enumerate(rows, 1):
        workspace_name = row.get("Workspace", "")
        report_id = row.get("Report ID", "").strip()
        report_name = row.get("Original Report Name", "")
        std_name = row.get("Standardized Report Name", "")
        theme = row.get("Theme Group", "")
        url = row.get("Report URL", "")
        ws_id = extract_ws_id(url)

        logger.info("[%d/%d] %-35s | %s", i, len(rows), workspace_name[:35], report_name[:50])
        notes: list[str] = []

        # ── Workspace members ─────────────────────────────────────────────────
        ws_users: list[dict] = []
        if ws_id:
            ws_users = scanner_ws_users.get(ws_id, [])
            if not ws_users:
                if ws_id not in ws_users_cache:
                    ws_users_cache[ws_id] = get_workspace_users_api(ws_id, credential)
                ws_users = ws_users_cache[ws_id]
                if ws_users:
                    notes.append("ws_users:fallback")
                else:
                    notes.append("ws_users:empty")
        else:
            cnt_personal += 1
            notes.append("personal-workspace")

        # ── Report direct users ───────────────────────────────────────────────
        rpt_scanner = scanner_reports.get(report_id, {})
        report_users: list[dict] = rpt_scanner.get("users", [])
        if not report_users and ws_id:
            report_users = get_report_users_api(report_id, credential)
            if report_users:
                notes.append("rpt_users:fallback")

        # ── Semantic model ────────────────────────────────────────────────────
        dataset_id = rpt_scanner.get("datasetId", "")
        if not dataset_id and ws_id:
            dataset_id = get_report_dataset_id(ws_id, report_id, credential)

        ds_scanner = scanner_datasets.get(dataset_id, {}) if dataset_id else {}
        dataset_mode = ds_scanner.get("defaultMode", "")

        dataset_users: list[dict] = ds_scanner.get("users", [])
        if not dataset_users and dataset_id:
            dataset_users = get_dataset_users_api(dataset_id, credential)
            if dataset_users:
                notes.append("ds_users:fallback")

        # ── Upstream lakehouse via Scanner lineage ────────────────────────────
        # upstreamArtifacts lists all upstream dependencies (Lakehouse, Warehouse, etc.)
        upstream = [
            a for a in ds_scanner.get("upstreamArtifacts", [])
            if a.get("type") in ("Lakehouse", "Warehouse", "SQLEndpoint")
        ]

        lakehouse_ws_id = ""
        lakehouse_ws_users: list[dict] = []
        lakehouse_names: list[str] = []
        upstream_artifact_ids: list[str] = []
        # (workspace_id, item_id) pairs — needed for /admin/workspaces/{ws}/items/{id}/users
        lakehouse_items: list[tuple[str, str]] = []

        if upstream:
            cnt_lh_found += 1
            if len(upstream) > 1:
                notes.append(f"multi-upstream:{len(upstream)}")

            upstream_artifact_ids = [a.get("artifactId", "") for a in upstream if a.get("artifactId")]
            for a in upstream:
                lh_ws = a.get("workspaceId", "")
                lh_id = a.get("artifactId", "")
                if lh_ws and lh_id:
                    lakehouse_items.append((lh_ws, lh_id))

            # Use the first upstream entry for workspace lookup
            lh = upstream[0]
            lakehouse_ws_id = lh.get("workspaceId", "")

            if lakehouse_ws_id:
                lh_ws_users = scanner_ws_users.get(lakehouse_ws_id, [])
                if not lh_ws_users:
                    if lakehouse_ws_id not in ws_users_cache:
                        ws_users_cache[lakehouse_ws_id] = get_workspace_users_api(
                            lakehouse_ws_id, credential
                        )
                    lh_ws_users = ws_users_cache[lakehouse_ws_id]
                    if lh_ws_users:
                        notes.append("lh_ws_users:fallback")
                lakehouse_ws_users = lh_ws_users

                lh_items = _ensure_ws_items(lakehouse_ws_id)
                lakehouse_names = [
                    f"{it.get('displayName', '?')} ({it.get('id', '?')})"
                    for it in lh_items
                    if it.get("type") == "Lakehouse"
                ]
        else:
            # No lineage from Scanner — check if a lakehouse lives in the same workspace
            if ws_id:
                same_ws_lh = [
                    it for it in _ensure_ws_items(ws_id)
                    if it.get("type") == "Lakehouse"
                ]
                if same_ws_lh:
                    lakehouse_ws_id = ws_id
                    lakehouse_ws_users = ws_users
                    lakehouse_names = [
                        f"{it.get('displayName', '?')} ({it.get('id', '?')})"
                        for it in same_ws_lh
                    ]
                    lakehouse_items = [(ws_id, it["id"]) for it in same_ws_lh if it.get("id")]
                    notes.append("lakehouse:same-ws-inferred")
                    cnt_lh_found += 1
                else:
                    notes.append("lakehouse:not-found")
                    cnt_lh_not_found += 1

        # ── Lakehouse item-level permissions ──────────────────────────────────
        # ReadAll = SQL analytics endpoint access = can query the Direct Lake model data.
        # Looks up pre-fetched cache first; falls back to a live call only for lakehouses
        # discovered via the same-workspace fallback (not in Scanner lineage).
        lakehouse_item_entries: list[dict] = []
        for lh_ws_id, lh_item_id in lakehouse_items:
            key = (lh_ws_id, lh_item_id)
            if key in lh_access_cache:
                entries = lh_access_cache[key]
            else:
                entries = get_lakehouse_item_access(lh_item_id, lh_ws_id, credential)
                lh_access_cache[key] = entries
                logger.debug(
                    "  Lakehouse %s (ws=%s) — %d access entries (live call)",
                    lh_item_id, lh_ws_id, len(entries)
                )
            lakehouse_item_entries.extend(entries)

        # Workspace roles that automatically grant SQL analytics endpoint (ReadAll) access.
        # Viewer role does NOT get ReadAll — they can open reports but cannot query the
        # SQL endpoint or read Delta files directly.
        _READALL_WS_ROLES = {"Admin", "Member", "Contributor"}
        lh_ws_readall = [
            u for u in lakehouse_ws_users
            if next((u[f] for f in _ROLE_FIELDS if f in u), "") in _READALL_WS_ROLES
        ]
        # Explicit ReadAll item shares (rare — direct lakehouse shares bypass workspace roles)
        explicit_readall = format_item_access(lakehouse_item_entries, access_type_filter="ReadAll")
        readall_parts = []
        if lh_ws_readall:
            readall_parts.append(format_users(lh_ws_readall))
        if explicit_readall:
            readall_parts.append(explicit_readall)

        output_rows.append({
            "Workspace": workspace_name,
            "Theme Group": theme,
            "Original Report Name": report_name,
            "Standardized Name": std_name,
            "Report ID": report_id,
            "Workspace ID": ws_id or "",
            "Workspace Members": format_users(ws_users),
            "Report Direct Users": format_users(report_users),
            "Semantic Model ID": dataset_id,
            "Semantic Model Mode": dataset_mode,
            "Semantic Model Direct Users": format_users(dataset_users),
            "Upstream Artifact IDs": "; ".join(upstream_artifact_ids),
            "Lakehouse Workspace ID": lakehouse_ws_id,
            "Lakehouse Same as Report WS": (
                "YES" if lakehouse_ws_id and lakehouse_ws_id == ws_id else
                "NO" if lakehouse_ws_id else ""
            ),
            "Lakehouse Workspace Members": format_users(lakehouse_ws_users),
            "Lakehouse Names": "; ".join(lakehouse_names),
            # All direct item shares (Read / ReadAll / Write / Reshare)
            "Lakehouse Item Permissions": format_item_access(lakehouse_item_entries),
            # Everyone who can query the lakehouse via SQL analytics endpoint:
            # workspace Admin/Member/Contributor (implicit ReadAll) + explicit ReadAll item shares
            "Lakehouse ReadAll (SQL Access)": "; ".join(readall_parts),
            "Notes": "; ".join(notes),
        })

    # Persist any workspace items fetched on-demand during Step 3
    if cached_items is None or len(ws_fabric_items) > len(cached_items or {}):
        _cache_save(CACHE_WS_ITEMS, ws_fabric_items)

    # ── Write output ──────────────────────────────────────────────────────────
    fieldnames = [
        "Workspace", "Theme Group", "Original Report Name", "Standardized Name",
        "Report ID", "Workspace ID",
        "Workspace Members",
        "Report Direct Users",
        "Semantic Model ID", "Semantic Model Mode", "Semantic Model Direct Users",
        "Upstream Artifact IDs",
        "Lakehouse Workspace ID", "Lakehouse Same as Report WS",
        "Lakehouse Workspace Members",
        "Lakehouse Names",
        # Item-level lakehouse permissions (direct shares, not workspace roles)
        "Lakehouse Item Permissions",
        # ReadAll = SQL analytics endpoint access = the people who can query Direct Lake data
        "Lakehouse ReadAll (SQL Access)",
        "Notes",
    ]

    out_path = Path(OUTPUT_CSV)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    logger.info("=" * 70)
    logger.info("Audit complete")
    logger.info("  Reports processed  : %d", len(output_rows))
    logger.info("  Lakehouse found    : %d", cnt_lh_found)
    logger.info("  Lakehouse not found: %d", cnt_lh_not_found)
    logger.info("  Personal workspace : %d (skipped)", cnt_personal)
    logger.info("  Output CSV : %s", out_path.resolve())
    logger.info("  Log file   : %s", Path(LOG_FILE).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
