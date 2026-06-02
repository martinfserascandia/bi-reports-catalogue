"""
Pre-flight check for report renaming.
Reads fabric_reports_20260504_140808.csv and verifies:
  1. Which reports will be renamed (excluding French Reporting and same-name rows)
  2. Whether each report still exists in the workspace
  3. Whether the current user has a role that permits renaming (Contributor or above)
Does NOT rename anything.
"""

import base64
import csv
import json
import os
import re
import sys
from pathlib import Path

import requests
from azure.identity import AzureCliCredential, ClientSecretCredential

FABRIC_REPORTS_CSV = "fabric_reports_20260504_140808.csv"
TENANT_ID_DEFAULT = "1dc7fe1c-3fd1-428f-b745-de881b406952"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"
PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Theme groups that must NOT be renamed
EXCLUDE_THEME_GROUPS = {"French Reporting"}

# Workspace roles that allow renaming items
RENAME_ROLES = {"Admin", "Member", "Contributor"}


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


def get_credential():
    tenant = os.getenv("AZURE_TENANT_ID", TENANT_ID_DEFAULT).strip()
    mode = os.getenv("FABRIC_AUTH_MODE", "azure_cli").strip().lower()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()
    # Rename checks must run as the human user — Azure CLI auth only.
    # Service principal is not a workspace member and cannot rename reports.
    if mode == "service_principal" and client_id and client_secret:
        print(f"Auth: service principal (tenant={tenant})")
        return ClientSecretCredential(tenant, client_id, client_secret)
    print("Auth: Azure CLI (your personal account — required for workspace role checks)")
    return AzureCliCredential(tenant_id=tenant)


def get_headers(credential) -> dict:
    token = credential.get_token(PBI_SCOPE)
    return {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}


def decode_upn(credential) -> str:
    """Extract UPN/email from the JWT access token (best-effort)."""
    try:
        token = credential.get_token(PBI_SCOPE)
        parts = token.token.split(".")
        if len(parts) < 2:
            return "<unknown>"
        # Pad and decode the payload section
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = json.loads(base64.b64decode(payload))
        return claims.get("upn") or claims.get("unique_name") or claims.get("email") or "<unknown>"
    except Exception:
        return "<unknown>"


def extract_workspace_id(url: str):
    """Return workspace ID from a Power BI URL, or None for My Workspace URLs."""
    m = re.search(r'/groups/([0-9a-f-]{36})/reports/', url or "")
    return m.group(1) if m else None


def pbi_get(url: str, headers: dict) -> tuple[int, dict | None]:
    try:
        r = requests.get(url, headers=headers, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception as e:
        return -1, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _load_env(Path(".env"))
    credential = get_credential()
    headers = get_headers(credential)
    current_user = decode_upn(credential)
    print(f"Current user: {current_user}\n")

    # -----------------------------------------------------------------------
    # Load and classify CSV rows
    # -----------------------------------------------------------------------
    csv_path = Path(FABRIC_REPORTS_CSV)
    if not csv_path.exists():
        print(f"ERROR: {FABRIC_REPORTS_CSV} not found in current directory.")
        sys.exit(1)

    all_rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)

    excluded_french = []
    excluded_same_name = []
    excluded_my_workspace = []
    excluded_empty = []
    to_rename = []

    for row in all_rows:
        theme = (row.get("Theme Group") or "").strip()
        orig  = (row.get("Original Report Name") or "").strip()
        std   = (row.get("Standardized Report Name") or "").strip()
        rid   = (row.get("Report ID") or "").strip()
        url   = (row.get("Report URL") or "").strip()

        if not rid:
            excluded_empty.append(row)
            continue

        if theme in EXCLUDE_THEME_GROUPS:
            excluded_french.append(row)
            continue

        if not std or orig == std:
            excluded_same_name.append(row)
            continue

        ws_id = extract_workspace_id(url)
        if ws_id is None:
            excluded_my_workspace.append(row)
            continue

        to_rename.append({**row, "_ws_id": ws_id})

    print("=" * 65)
    print("CLASSIFICATION SUMMARY")
    print("=" * 65)
    print(f"  Total rows in CSV              : {len(all_rows)}")
    print(f"  Excluded (French Reporting)    : {len(excluded_french)}  <-- WILL NOT be renamed")
    print(f"  Excluded (name already correct): {len(excluded_same_name)}")
    print(f"  Excluded (My Workspace)        : {len(excluded_my_workspace)}  <-- personal workspace, check manually")
    print(f"  Excluded (empty rows)          : {len(excluded_empty)}")
    print(f"  Reports to rename              : {len(to_rename)}")
    print()

    if excluded_french:
        print("French Reporting reports (EXCLUDED — will not be touched):")
        for r in excluded_french:
            print(f"    [{r.get('Workspace')}] {r.get('Original Report Name')!r}")
        print()

    if excluded_my_workspace:
        print("My Workspace reports (need manual review — not in a shared workspace):")
        for r in excluded_my_workspace:
            print(f"    {r.get('Original Report Name')!r} -> {r.get('Standardized Report Name')!r}  (ID: {r.get('Report ID')})")
        print()

    if not to_rename:
        print("Nothing to rename. Done.")
        return

    # -----------------------------------------------------------------------
    # Per-workspace role check
    # -----------------------------------------------------------------------
    unique_ws_ids = {r["_ws_id"] for r in to_rename}
    print("=" * 65)
    print(f"WORKSPACE PERMISSION CHECK  ({len(unique_ws_ids)} unique workspaces)")
    print("=" * 65)

    ws_role: dict[str, str] = {}   # ws_id -> role string or "NO ACCESS"
    ws_name: dict[str, str] = {}   # ws_id -> display name

    for ws_id in sorted(unique_ws_ids):
        status, data = pbi_get(f"{PBI_BASE}/groups/{ws_id}/users", headers)
        if status == 200 and data:
            users = data.get("value", [])
            my_role = "NOT FOUND"
            for u in users:
                upn = (u.get("emailAddress") or u.get("identifier") or "").strip().lower()
                if upn == current_user.lower():
                    my_role = u.get("groupUserAccessRight") or u.get("principalType") or "unknown"
                    break
            # If service principal is used, match by identifier instead of email
            if my_role == "NOT FOUND":
                sp_id = os.getenv("AZURE_CLIENT_ID", "").strip().lower()
                for u in users:
                    ident = (u.get("identifier") or "").strip().lower()
                    if sp_id and ident == sp_id:
                        my_role = u.get("groupUserAccessRight") or "unknown"
                        break
            ws_role[ws_id] = my_role
        elif status == 403:
            ws_role[ws_id] = "403 FORBIDDEN"
        elif status == 404:
            ws_role[ws_id] = "404 NOT FOUND"
        else:
            ws_role[ws_id] = f"HTTP {status}"

    # -----------------------------------------------------------------------
    # Per-report existence check
    # -----------------------------------------------------------------------
    print()
    print("=" * 65)
    print(f"REPORT EXISTENCE CHECK  ({len(to_rename)} reports)")
    print("=" * 65)
    print()

    ok_count = 0
    warn_count = 0
    err_count = 0

    results = []
    for r in to_rename:
        ws_id  = r["_ws_id"]
        rid    = r["Report ID"].strip()
        orig   = r["Original Report Name"].strip()
        std    = r["Standardized Report Name"].strip()
        ws_lbl = r.get("Workspace", ws_id)
        theme  = r.get("Theme Group", "")

        role   = ws_role.get(ws_id, "?")
        can_rename = role in RENAME_ROLES

        status, data = pbi_get(f"{PBI_BASE}/groups/{ws_id}/reports/{rid}", headers)
        if status == 200 and data:
            current_name = (data.get("name") or data.get("displayName") or "").strip()
            name_match = current_name == orig
            exists = True
        elif status == 404:
            current_name = "<NOT FOUND>"
            name_match = False
            exists = False
        else:
            current_name = f"<HTTP {status}>"
            name_match = False
            exists = True  # assume exists, just can't verify

        results.append({
            "workspace": ws_lbl,
            "theme": theme,
            "orig": orig,
            "std": std,
            "rid": rid,
            "ws_id": ws_id,
            "role": role,
            "can_rename": can_rename,
            "exists": exists,
            "current_name": current_name,
            "name_match": name_match,
        })

        flag = "OK" if (exists and can_rename) else "WARN" if can_rename else "ERR"
        if flag == "OK":
            ok_count += 1
        elif flag == "WARN":
            warn_count += 1
        else:
            err_count += 1

        marker = " [OK]" if flag == "OK" else " [WARN - not found]" if flag == "WARN" else " [ERR - no permission]"
        print(f"  {marker}")
        print(f"    Workspace : {ws_lbl}  (role: {role})")
        print(f"    Rename    : {orig!r}  ->  {std!r}")
        if not name_match and exists:
            print(f"    WARNING   : current name in API is {current_name!r}  (mismatch with CSV)")
        print()

    # -----------------------------------------------------------------------
    # Final verdict
    # -----------------------------------------------------------------------
    print("=" * 65)
    print("FINAL VERDICT")
    print("=" * 65)
    print(f"  Ready to rename      : {ok_count}")
    print(f"  Report not found     : {warn_count}")
    print(f"  Insufficient role    : {err_count}")
    print()

    if err_count > 0:
        print("ACTION NEEDED: You do not have sufficient permissions in some workspaces.")
        print("               You need at least Contributor role to rename reports.")
    elif warn_count > 0:
        print("ACTION NEEDED: Some reports were not found (may have been deleted or moved).")
        print("               Review the WARN rows above before proceeding.")
    else:
        print("All checks passed. Safe to proceed with renaming.")
        print()
        print("To rename, run:  python rename_reports.py")
        print("(that script will be created as the next step)")


if __name__ == "__main__":
    main()
