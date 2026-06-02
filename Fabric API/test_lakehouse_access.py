"""Quick test: call the Fabric Admin item-access endpoint and print the raw response."""

import json
import os
from pathlib import Path

import requests
from azure.identity import AzureCliCredential, ClientSecretCredential

TENANT_ID = "1dc7fe1c-3fd1-428f-b745-de881b406952"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# A few real lakehouses from the last audit run (workspace_id, lakehouse_id, label)
TEST_LAKEHOUSES = [
    ("2f79a991-b0a5-417f-b9e9-d83e68f14efa", "3251d0d6-d2ad-4738-940d-16ff2fe22436", "Budget_LH"),
    ("fa600ff6-3b68-4b68-af30-710dc7322791", "8c78787b-606a-4c60-bac7-d84e9eb6195c", "SCH"),
]

def test_url(label, url, headers):
    print(f"=== {label} ===================================")
    print(f"   URL: {url}")
    resp = requests.get(url, headers=headers, timeout=30)
    print(f"   Status: {resp.status_code}")
    try:
        body = resp.json()
        print(f"   Response keys: {list(body.keys())}")
        print(f"   Full response:\n{json.dumps(body, indent=2)[:2000]}")
    except Exception:
        print(f"   Raw text: {resp.text[:500]}")
    print()

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

    # Use local az profile if present
    local_az = Path.cwd() / ".az-fabric"
    if local_az.exists():
        os.environ["AZURE_CONFIG_DIR"] = str(local_az)

    tenant_id = os.getenv("AZURE_TENANT_ID", TENANT_ID).strip()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        print(f"Auth: service principal (tenant={tenant_id})")
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        print("Auth: Azure CLI (set AZURE_CLIENT_ID + AZURE_CLIENT_SECRET to use service principal)")
        credential = AzureCliCredential(tenant_id=tenant_id)

    fabric_token = credential.get_token(FABRIC_SCOPE)
    pbi_token = credential.get_token(PBI_SCOPE)
    fabric_headers = {"Authorization": f"Bearer {fabric_token.token}", "Content-Type": "application/json"}
    pbi_headers = {"Authorization": f"Bearer {pbi_token.token}", "Content-Type": "application/json"}
    print(f"Tokens acquired\n")

    ws_id, lh_id, label = TEST_LAKEHOUSES[0]

    print("--- Test 1: Fabric scope, Fabric Admin endpoint ---")
    test_url(label, f"{FABRIC_BASE}/admin/workspaces/{ws_id}/items/{lh_id}/users", fabric_headers)

    print("--- Test 2: PBI scope, Fabric Admin endpoint ---")
    test_url(label, f"{FABRIC_BASE}/admin/workspaces/{ws_id}/items/{lh_id}/users", pbi_headers)

    print("--- Test 3: Fabric scope, non-admin endpoint (caller must be workspace member) ---")
    test_url(label, f"{FABRIC_BASE}/workspaces/{ws_id}/lakehouses/{lh_id}/users", fabric_headers)

    print("--- Test 4: PBI scope, PBI Admin groups users (workspace-level, sanity check) ---")
    test_url("workspace-users", f"{PBI_BASE}/admin/groups/{ws_id}/users", pbi_headers)

if __name__ == "__main__":
    main()
