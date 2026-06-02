"""Single-report rename test: F8_Consolidated -> Forma 8 Consolidated Overview."""

import json
import os
from pathlib import Path

import requests
from azure.identity import AzureCliCredential, ClientSecretCredential

WORKSPACE_ID = "f78e1c50-1537-49a4-a1bc-10c414e74c0f"
REPORT_ID    = "298bbd42-c7f5-4491-a73d-9057ab3ce76f"
NEW_NAME     = "Forma 8 Consolidated Overview"

TENANT_ID_DEFAULT = "1dc7fe1c-3fd1-428f-b745-de881b406952"
FABRIC_BASE  = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    _load_env(Path(".env"))

    tenant = os.getenv("AZURE_TENANT_ID", TENANT_ID_DEFAULT).strip()
    mode   = os.getenv("FABRIC_AUTH_MODE", "azure_cli").strip().lower()

    # Always use Azure CLI for rename — the service principal is not a workspace member
    print("Auth: Azure CLI")
    credential = AzureCliCredential(tenant_id=tenant)

    try:
        token = credential.get_token(FABRIC_SCOPE)
    except Exception as e:
        print(f"ERROR: Could not get token.\n  {e}")
        print()
        print("Run:  az login --tenant", tenant)
        return

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    item_url = f"{FABRIC_BASE}/workspaces/{WORKSPACE_ID}/items/{REPORT_ID}"

    # Step 1 — read current state
    print(f"Checking current report name...")
    r = requests.get(item_url, headers=headers, timeout=30)
    print(f"  GET status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        current_name = data.get("displayName") or data.get("name") or "<unknown>"
        print(f"  Current name: {current_name!r}")
        if current_name == NEW_NAME:
            print("  Already has the target name — nothing to do.")
            return
    elif r.status_code == 401:
        print("  401 Unauthorized — token may be expired. Run: az login --tenant", tenant)
        print(f"  Response: {r.text[:300]}")
        return
    elif r.status_code == 403:
        print("  403 Forbidden — insufficient permissions on this workspace.")
        print(f"  Response: {r.text[:300]}")
        return
    elif r.status_code == 404:
        print("  404 — report not found (may have been deleted or moved).")
        return
    else:
        print(f"  Unexpected status {r.status_code}: {r.text[:300]}")
        return

    # Step 2 — rename
    print(f"\nRenaming to: {NEW_NAME!r}")
    r2 = requests.patch(
        item_url,
        headers=headers,
        json={"displayName": NEW_NAME},
        timeout=30,
    )
    print(f"  PATCH status: {r2.status_code}")

    if r2.status_code in (200, 204):
        print("  SUCCESS - report renamed.")
        if r2.text.strip():
            try:
                print(f"  Response: {json.dumps(r2.json(), indent=2)[:500]}")
            except Exception:
                print(f"  Response: {r2.text[:300]}")
    else:
        print(f"  FAILED: {r2.text[:500]}")


if __name__ == "__main__":
    main()
