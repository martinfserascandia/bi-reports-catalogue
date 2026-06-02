"""
Bulk report rename from fabric_reports_20260504_140808.csv.
Skips French Reporting and rows where the name is already correct.
Uses Azure CLI auth (your personal account).
Writes a summary log to rename_reports_YYYYMMDD_HHMMSS.log.
"""

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from azure.identity import AzureCliCredential

FABRIC_REPORTS_CSV = "fabric_reports_20260504_140808.csv"
TENANT_ID_DEFAULT  = "1dc7fe1c-3fd1-428f-b745-de881b406952"
FABRIC_BASE        = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE       = "https://api.fabric.microsoft.com/.default"

EXCLUDE_THEME_GROUPS = {"French Reporting"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def extract_workspace_id(url: str):
    m = re.search(r'/groups/([0-9a-f-]{36})/reports/', url or "")
    return m.group(1) if m else None


def get_personal_workspace_id(headers: dict) -> str | None:
    """Return the current user's personal workspace ID, or None if not found."""
    try:
        r = requests.get(f"{FABRIC_BASE}/workspaces", headers=headers, timeout=30)
        if r.status_code != 200:
            return None
        for ws in r.json().get("value", []):
            if ws.get("type") in ("PersonalWorkspace", "Personal"):
                return ws.get("id")
    except Exception:
        pass
    return None


def rename_item(workspace_id: str, item_id: str, new_name: str, headers: dict) -> tuple[bool, str]:
    """
    PATCH the item displayName. Returns (success, message).
    """
    url = f"{FABRIC_BASE}/workspaces/{workspace_id}/items/{item_id}"
    try:
        r = requests.patch(url, headers=headers, json={"displayName": new_name}, timeout=30)
        if r.status_code in (200, 204):
            return True, f"OK ({r.status_code})"
        else:
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:300]
            return False, f"HTTP {r.status_code}: {detail}"
    except Exception as e:
        return False, f"Exception: {e}"


def verify_current_name(workspace_id: str, item_id: str, headers: dict) -> str | None:
    """Return the current displayName of the item, or None on error."""
    url = f"{FABRIC_BASE}/workspaces/{workspace_id}/items/{item_id}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get("displayName") or data.get("name")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _load_env(Path(".env"))

    tenant = os.getenv("AZURE_TENANT_ID", TENANT_ID_DEFAULT).strip()

    print("Auth: Azure CLI")
    credential = AzureCliCredential(tenant_id=tenant)
    try:
        token = credential.get_token(FABRIC_SCOPE)
    except Exception as e:
        print(f"ERROR: Could not get token — {e}")
        print(f"Run:  az login --tenant {tenant}")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    # Resolve personal workspace ID (for "My workspace" reports)
    print("Resolving personal workspace ID...")
    personal_ws_id = get_personal_workspace_id(headers)
    if personal_ws_id:
        print(f"  Personal workspace: {personal_ws_id}")
    else:
        print("  Could not resolve personal workspace — My Workspace reports will be skipped.")
    print()

    # Load CSV
    csv_path = Path(FABRIC_REPORTS_CSV)
    if not csv_path.exists():
        print(f"ERROR: {FABRIC_REPORTS_CSV} not found.")
        sys.exit(1)

    all_rows = []
    with open(csv_path, encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    # Categorize
    to_rename = []
    skipped_french = []
    skipped_same   = []
    skipped_my_ws  = []
    skipped_empty  = []

    for row in all_rows:
        theme = (row.get("Theme Group") or "").strip()
        orig  = (row.get("Original Report Name") or "").strip()
        std   = (row.get("Standardized Report Name") or "").strip()
        rid   = (row.get("Report ID") or "").strip()
        url   = (row.get("Report URL") or "").strip()
        ws_lbl = (row.get("Workspace") or "").strip()

        if not rid:
            skipped_empty.append(row)
            continue

        if theme in EXCLUDE_THEME_GROUPS:
            skipped_french.append(row)
            continue

        if not std or orig == std:
            skipped_same.append(row)
            continue

        ws_id = extract_workspace_id(url)
        if ws_id is None:
            if personal_ws_id:
                ws_id = personal_ws_id
            else:
                skipped_my_ws.append(row)
                continue

        to_rename.append({
            "ws_id":  ws_id,
            "rid":    rid,
            "orig":   orig,
            "std":    std,
            "ws_lbl": ws_lbl,
            "theme":  theme,
        })

    print("=" * 65)
    print("RENAME PLAN")
    print("=" * 65)
    print(f"  To rename              : {len(to_rename)}")
    print(f"  Skipped (French)       : {len(skipped_french)}  -- excluded by policy")
    print(f"  Skipped (same name)    : {len(skipped_same)}")
    print(f"  Skipped (My Workspace) : {len(skipped_my_ws)}")
    print(f"  Skipped (empty rows)   : {len(skipped_empty)}")
    print()

    if not to_rename:
        print("Nothing to rename.")
        return

    # Confirm before proceeding
    print("Reports to rename:")
    for r in to_rename:
        print(f"  [{r['ws_lbl']}]  {r['orig']!r}  ->  {r['std']!r}")
    print()

    # Run renames
    log_path = Path(f"rename_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_lines = [f"Rename run started: {datetime.now().isoformat()}\n"]

    ok_count   = 0
    fail_count = 0
    skip_count = 0

    print("=" * 65)
    print("RENAMING")
    print("=" * 65)

    for i, r in enumerate(to_rename, 1):
        ws_id = r["ws_id"]
        rid   = r["rid"]
        orig  = r["orig"]
        std   = r["std"]
        label = f"[{i}/{len(to_rename)}] [{r['ws_lbl']}] {orig!r}"

        # Verify current name before renaming (safety check)
        current = verify_current_name(ws_id, rid, headers)
        if current is None:
            msg = "SKIP — could not read report (may not exist or no access)"
            print(f"  {label}")
            print(f"    {msg}")
            log_lines.append(f"SKIP  | {r['ws_lbl']} | {rid} | {orig} | {std} | {msg}\n")
            skip_count += 1
            continue

        if current == std:
            msg = "SKIP — already has target name"
            print(f"  {label}")
            print(f"    {msg}")
            log_lines.append(f"SKIP  | {r['ws_lbl']} | {rid} | {orig} | {std} | {msg}\n")
            skip_count += 1
            continue

        if current != orig:
            # Name in API differs from CSV — rename anyway (CSV target name is authoritative)
            print(f"  {label}")
            print(f"    NOTE: current API name is {current!r} (differs from CSV original)")

        success, detail = rename_item(ws_id, rid, std, headers)
        if success:
            print(f"  {label}")
            print(f"    OK  ->  {std!r}")
            log_lines.append(f"OK    | {r['ws_lbl']} | {rid} | {orig} | {std}\n")
            ok_count += 1
        else:
            print(f"  {label}")
            print(f"    FAIL: {detail}")
            log_lines.append(f"FAIL  | {r['ws_lbl']} | {rid} | {orig} | {std} | {detail}\n")
            fail_count += 1

    # Summary
    print()
    print("=" * 65)
    print("DONE")
    print("=" * 65)
    print(f"  Renamed successfully : {ok_count}")
    print(f"  Failed               : {fail_count}")
    print(f"  Skipped              : {skip_count}")

    log_lines.append(f"\nSummary: OK={ok_count}  FAIL={fail_count}  SKIP={skip_count}\n")
    log_path.write_text("".join(log_lines), encoding="utf-8")
    print(f"\nLog written to: {log_path}")

    if skipped_my_ws:
        print()
        print("My Workspace reports not renamed (no workspace ID resolved):")
        for r in skipped_my_ws:
            print(f"  {r.get('Original Report Name')!r} -> {r.get('Standardized Report Name')!r}")

    if skipped_french:
        print()
        print(f"French Reporting reports intentionally excluded: {len(skipped_french)}")


if __name__ == "__main__":
    main()
