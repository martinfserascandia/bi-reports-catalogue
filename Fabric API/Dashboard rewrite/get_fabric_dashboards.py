"""
get_fabric_dashboards.py
Fetch all report names from Microsoft Fabric.

Authentication options:
  1. Service Principal (recommended for automation)
  2. Azure CLI (for local/interactive use)

Requirements:
    pip install azure-identity requests tabulate
"""

import csv
import datetime
import os
import sys
import time
from pathlib import Path

import requests
from tabulate import tabulate


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from a .env file into process env."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def configure_runtime() -> None:
    """Load env files and prefer the repo-local Azure CLI profile when present."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    load_env_file(repo_root / ".env")
    load_env_file(script_dir / ".env")

    if not os.getenv("AZURE_CONFIG_DIR"):
        local_az_config = repo_root / ".az-fabric"
        if local_az_config.exists():
            os.environ["AZURE_CONFIG_DIR"] = str(local_az_config)


def get_access_token() -> str:
    """
    Return a bearer token for the Microsoft Fabric REST API.

    Priority:
      1. Service Principal via env vars
         (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)
      2. Azure CLI credential (az login)
    """
    scope = "https://api.fabric.microsoft.com/.default"

    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()

    if tenant_id and client_id and client_secret:
        from azure.identity import ClientSecretCredential

        print("Authenticating via service principal...")
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    else:
        from azure.identity import AzureCliCredential

        print("Authenticating via Azure CLI (az login)...")
        credential = AzureCliCredential(tenant_id=tenant_id or None)

    token = credential.get_token(scope)
    return token.token


BASE_URL = "https://api.fabric.microsoft.com/v1"


def api_get(token: str, path: str) -> dict:
    """Authenticated GET against the Fabric REST API."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}{path}"
    max_attempts = 6

    for attempt in range(1, max_attempts + 1):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()

        retry_after = resp.headers.get("Retry-After", "").strip()
        try:
            wait_seconds = int(retry_after) if retry_after else min(5 * attempt, 30)
        except ValueError:
            wait_seconds = min(5 * attempt, 30)

        print(
            f"Rate limited on {path}. Waiting {wait_seconds}s before retry "
            f"({attempt}/{max_attempts})..."
        )
        time.sleep(wait_seconds)

    resp.raise_for_status()
    return resp.json()


def paged_get(token: str, path: str) -> list[dict]:
    """Follow Fabric continuation tokens and return all rows."""
    rows: list[dict] = []
    next_path = path

    while next_path:
        data = api_get(token, next_path)
        rows.extend(data.get("value", []))

        continuation_token = data.get("continuationToken")
        if continuation_token:
            separator = "&" if "?" in path else "?"
            next_path = f"{path}{separator}continuationToken={continuation_token}"
        else:
            next_path = ""

    return rows


def get_all_workspaces(token: str) -> list[dict]:
    """Return all workspaces the caller can access in Fabric."""
    return paged_get(token, "/workspaces")


def get_reports_in_workspace(token: str, workspace_id: str) -> list[dict]:
    """Return reports inside a single Fabric workspace."""
    try:
        return paged_get(token, f"/workspaces/{workspace_id}/reports")
    except requests.HTTPError as exc:
        print(f"Warning: skipping workspace {workspace_id}: {exc}")
        return []


def build_report_url(workspace_id: str, report_id: str, workspace_type: str) -> str:
    """
    Build the standard Power BI web URL for a report.

    Fabric's report APIs return the IDs we need, while Power BI's report APIs
    document the corresponding webUrl shape.
    """
    if workspace_type.lower() == "personal":
        return f"https://app.powerbi.com/reports/{report_id}"
    return f"https://app.powerbi.com/groups/{workspace_id}/reports/{report_id}"


def main() -> None:
    configure_runtime()

    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip() or "<not set>"
    azure_config_dir = os.getenv("AZURE_CONFIG_DIR", "").strip() or "<default profile>"
    print(f"Azure tenant: {tenant_id}")
    print(f"Azure CLI profile: {azure_config_dir}")

    token = get_access_token()

    all_rows = []

    print("Fetching workspaces...")
    workspaces = get_all_workspaces(token)
    print(f"Found {len(workspaces)} workspace(s). Scanning for reports...\n")

    for workspace in workspaces:
        workspace_id = workspace["id"]
        workspace_name = workspace.get("displayName", workspace_id)
        workspace_type = workspace.get("type", "Unknown")
        reports = get_reports_in_workspace(token, workspace_id)
        print(
            f"Workspace '{workspace_name}' ({workspace_type}) -> {len(reports)} report(s)"
        )
        for report in reports:
            report_id = report.get("id", "-")
            all_rows.append(
                (
                    workspace_name,
                    report.get("displayName", "-"),
                    report_id,
                    build_report_url(workspace_id, report_id, workspace_type),
                )
            )
        time.sleep(0.2)

    if not all_rows:
        print("No reports found.")
        sys.exit(0)

    all_rows.sort(key=lambda row: (row[0].lower(), row[1].lower()))

    print(f"\n{'-' * 70}")
    print(f"Total reports found: {len(all_rows)}")
    print(f"{'-' * 70}\n")
    print(
        tabulate(
            all_rows,
            headers=["Workspace", "Report Name", "Report ID", "Report URL"],
            tablefmt="pretty",
        )
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"fabric_reports_{timestamp}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(["Workspace", "Report Name", "Report ID", "Report URL"])
        writer.writerows(all_rows)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
