# Notebook Environment Variables

Use these variables with `fabric_migration_test.py` so configuration stays centralized.

## 1. Required Variables

- `FABRIC_DEST_WORKSPACE_ID` or `FABRIC_DEST_WORKSPACE_NAME`
- `FABRIC_REPOSITORY_DIRECTORY`
- `FABRIC_ENVIRONMENT`
- `FABRIC_AUTH_MODE` (`azure_cli`, `default`, or `service_principal`)
- `AZURE_TENANT_ID` (required when `FABRIC_AUTH_MODE=azure_cli`)

For your current migration test:

- `FABRIC_DEST_WORKSPACE_NAME=konsolidator` (destination)
- `FABRIC_SOURCE_WORKSPACE_NAME=konsolidator_dev` (source, read-only comparison)
- `FABRIC_ENVIRONMENT=MIGRATION`

## 2. Service Principal Only

Only required when `FABRIC_AUTH_MODE=service_principal`:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

## 3. Template File

Use `.env.example` as the source of truth. Create your own `.env` from it:

```powershell
Copy-Item .env.example .env
```

## 4. Load Variables In PowerShell

Option A (manual):

```powershell
$env:FABRIC_DEST_WORKSPACE_NAME="konsolidator"
$env:FABRIC_SOURCE_WORKSPACE_NAME="konsolidator_dev"
$env:FABRIC_REPOSITORY_DIRECTORY="C:\path\to\fabric-repo"
$env:FABRIC_ENVIRONMENT="MIGRATION"
$env:FABRIC_AUTH_MODE="azure_cli"
$env:AZURE_TENANT_ID="1dc7fe1c-3fd1-428f-b745-de881b406952"
$env:AZURE_CONFIG_DIR="$PWD\.az-fabric"
```

Option B (load from `.env` file):

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $name, $value = $_ -split '=', 2
  Set-Item -Path "Env:$name" -Value $value
}
```

## 5. Quick Check

Before running the notebook:

```powershell
echo $env:FABRIC_DEST_WORKSPACE_NAME
echo $env:FABRIC_SOURCE_WORKSPACE_NAME
echo $env:FABRIC_AUTH_MODE
echo $env:FABRIC_REPOSITORY_DIRECTORY
```

## 6. Script Run

Run the migration test script:

```powershell
python .\fabric_migration_test.py
```

The script writes detailed logs to:

```text
fabric_migration_test.log
```

## 7. Safety Flags

- `RUN_PUBLISH=false` by default
- `RUN_UNPUBLISH=false` by default
- `CONFIRM_UNPUBLISH=true` is required if you set `RUN_UNPUBLISH=true`

## 8. Security

Do not commit real secrets in `.env`.
