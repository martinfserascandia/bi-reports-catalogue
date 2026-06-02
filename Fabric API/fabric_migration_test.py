"""Fabric migration validation and deployment script.

This script replaces the notebook flow with a deterministic terminal workflow.
It performs:
1) Environment and auth setup
2) Token validation
3) Input validation sanity check
4) Target workspace initialization
5) Source vs target inventory comparison
6) Read-only API smoke checks
7) Feature-flag safety test
8) Optional publish and unpublish (disabled by default)
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Optional

from azure.identity import AzureCliCredential, ClientSecretCredential, DefaultAzureCredential
from fabric_cicd import (
    FabricWorkspace,
    append_feature_flag,
    publish_all_items,
    unpublish_all_orphan_items,
)
from fabric_cicd import constants
from fabric_cicd._common._exceptions import InputError
from fabric_cicd.constants import FeatureFlag


# ----------------------------
# Logging configuration
# ----------------------------
LOG_FILE = "fabric_migration_test.log"
logger = logging.getLogger("fabric_migration_test")
logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
_stream = logging.StreamHandler(sys.stdout)
_stream.setFormatter(_formatter)
_file = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file.setFormatter(_formatter)
logger.handlers.clear()
logger.addHandler(_stream)
logger.addHandler(_file)


def _print_header(title: str) -> None:
    logger.info("=" * 80)
    logger.info(title)
    logger.info("=" * 80)


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv(value: Optional[str], default: Iterable[str]) -> list[str]:
    if not value:
        return list(default)
    return [part.strip() for part in value.split(",") if part.strip()]


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load key=value pairs from a .env file into process environment."""
    loaded: Dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value
        loaded[key] = value
    return loaded


def _get_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _first_env(*names: str) -> str:
    """Return the first non-empty environment variable value from a list of names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _build_credential(auth_mode: str):
    """Create the token credential based on configured auth mode."""
    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()

    if auth_mode == "service_principal":
        logger.info("Auth mode: service_principal")
        return ClientSecretCredential(
            tenant_id=_get_required("AZURE_TENANT_ID"),
            client_id=_get_required("AZURE_CLIENT_ID"),
            client_secret=_get_required("AZURE_CLIENT_SECRET"),
        )

    if auth_mode == "default":
        logger.info("Auth mode: default")
        return DefaultAzureCredential()

    logger.info("Auth mode: azure_cli")
    if not tenant_id:
        raise ValueError("AZURE_TENANT_ID is required when FABRIC_AUTH_MODE=azure_cli")
    logger.info("Using Azure CLI tenant: %s", tenant_id)
    return AzureCliCredential(tenant_id=tenant_id)


def _validate_runtime_settings() -> dict:
    """Read and validate env config required by this script."""
    # Preferred variable names are FABRIC_DEST_* and FABRIC_SOURCE_*.
    # Legacy names are still accepted as fallback for compatibility.
    dest_workspace_id = _first_env("FABRIC_DEST_WORKSPACE_ID", "FABRIC_WORKSPACE_ID")
    dest_workspace_name = _first_env("FABRIC_DEST_WORKSPACE_NAME", "FABRIC_WORKSPACE_NAME")
    if not dest_workspace_id and not dest_workspace_name:
        raise ValueError("Set FABRIC_DEST_WORKSPACE_ID or FABRIC_DEST_WORKSPACE_NAME")

    repository_directory = _get_required("FABRIC_REPOSITORY_DIRECTORY")
    repo_path = Path(repository_directory)
    if not repo_path.exists():
        raise ValueError(f"FABRIC_REPOSITORY_DIRECTORY does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise ValueError(f"FABRIC_REPOSITORY_DIRECTORY is not a directory: {repo_path}")

    auth_mode = os.getenv("FABRIC_AUTH_MODE", "azure_cli").strip().lower()
    if auth_mode not in {"azure_cli", "default", "service_principal"}:
        raise ValueError("FABRIC_AUTH_MODE must be one of: azure_cli, default, service_principal")

    item_types = _parse_csv(
        os.getenv("FABRIC_ITEM_TYPES_SCOPE"),
        default=["Notebook", "DataPipeline", "Dataflow", "Lakehouse", "SemanticModel", "Report", "Environment"],
    )

    return {
        "dest_workspace_id": dest_workspace_id,
        "dest_workspace_name": dest_workspace_name,
        "source_workspace_id": _first_env("FABRIC_SOURCE_WORKSPACE_ID"),
        "source_workspace_name": _first_env("FABRIC_SOURCE_WORKSPACE_NAME"),
        "environment": os.getenv("FABRIC_ENVIRONMENT", "MIGRATION").strip(),
        "repository_directory": str(repo_path),
        "auth_mode": auth_mode,
        "parameter_file_path": os.getenv("FABRIC_PARAMETER_FILE_PATH", "").strip(),
        "run_publish": _parse_bool(os.getenv("RUN_PUBLISH"), default=False),
        "run_unpublish": _parse_bool(os.getenv("RUN_UNPUBLISH"), default=False),
        "confirm_unpublish": _parse_bool(os.getenv("CONFIRM_UNPUBLISH"), default=False),
        "item_types": item_types,
    }


def main() -> int:
    try:
        _print_header("FABRIC MIGRATION TEST SCRIPT START")

        # Section 1: Load .env and configure Azure CLI profile directory
        loaded = _load_env_file(Path(".env"))
        logger.info("Loaded %d variables from .env", len(loaded))
        if not os.getenv("AZURE_CONFIG_DIR"):
            local_az_cfg = Path.cwd() / ".az-fabric"
            if local_az_cfg.exists():
                os.environ["AZURE_CONFIG_DIR"] = str(local_az_cfg)
        logger.info("AZURE_CONFIG_DIR=%s", os.getenv("AZURE_CONFIG_DIR", "<not set>"))

        # Section 2: Validate runtime settings and create credential
        cfg = _validate_runtime_settings()
        credential = _build_credential(cfg["auth_mode"])
        logger.info(
            "Destination workspace identifier: %s",
            cfg["dest_workspace_id"] or cfg["dest_workspace_name"],
        )
        logger.info(
            "Source workspace identifier: %s",
            cfg["source_workspace_id"] or cfg["source_workspace_name"] or "<none>",
        )
        logger.info("Repository directory: %s", cfg["repository_directory"])
        logger.info("Environment: %s", cfg["environment"])
        logger.info("Item types in scope: %s", ", ".join(cfg["item_types"]))

        # Section 3: Token acquisition test
        _print_header("TOKEN TEST")
        token = credential.get_token("https://api.fabric.microsoft.com/.default")
        logger.info("Token acquired. expires_on=%s", token.expires_on)

        # Section 4: Negative test for workspace_id validation
        _print_header("INPUT VALIDATION TEST")
        try:
            FabricWorkspace(
                workspace_id="not-a-guid",
                repository_directory=cfg["repository_directory"],
                environment=cfg["environment"],
                token_credential=credential,
            )
            raise AssertionError("Expected InputError for invalid workspace_id")
        except InputError as ex:
            logger.info("PASS invalid workspace_id validation: %s", ex)

        # Section 5: Initialize target workspace object
        _print_header("TARGET WORKSPACE INIT")
        fw_kwargs = {
            "repository_directory": cfg["repository_directory"],
            "environment": cfg["environment"],
            "item_type_in_scope": cfg["item_types"],
            "token_credential": credential,
        }
        if cfg["parameter_file_path"]:
            fw_kwargs["parameter_file_path"] = cfg["parameter_file_path"]
        if cfg["dest_workspace_id"]:
            fw_kwargs["workspace_id"] = cfg["dest_workspace_id"]
        else:
            fw_kwargs["workspace_name"] = cfg["dest_workspace_name"]

        target_workspace = FabricWorkspace(**fw_kwargs)
        logger.info("Resolved destination workspace_id=%s", target_workspace.workspace_id)

        # Section 6: Optional source/target inventory comparison (read-only)
        _print_header("SOURCE VS TARGET COMPARISON (READ-ONLY)")
        if cfg["source_workspace_id"] or cfg["source_workspace_name"]:
            source_identifier = (
                {"workspace_id": cfg["source_workspace_id"]}
                if cfg["source_workspace_id"]
                else {"workspace_name": cfg["source_workspace_name"]}
            )
            source_workspace = FabricWorkspace(
                repository_directory=cfg["repository_directory"],
                environment=cfg["environment"],
                token_credential=credential,
                **source_identifier,
            )
            src_items = source_workspace.endpoint.invoke(
                method="GET",
                url=f"{constants.DEFAULT_API_ROOT_URL}/v1/workspaces/{source_workspace.workspace_id}/items",
            )["body"].get("value", [])
            tgt_items = target_workspace.endpoint.invoke(
                method="GET",
                url=f"{constants.DEFAULT_API_ROOT_URL}/v1/workspaces/{target_workspace.workspace_id}/items",
            )["body"].get("value", [])
            src_counts = Counter(item.get("type", "Unknown") for item in src_items)
            tgt_counts = Counter(item.get("type", "Unknown") for item in tgt_items)
            logger.info(
                "Source workspace: %s (%s)",
                cfg["source_workspace_id"] or cfg["source_workspace_name"],
                source_workspace.workspace_id,
            )
            logger.info("Destination workspace: %s", target_workspace.workspace_id)
            logger.info("Source item count: %d", len(src_items))
            logger.info("Target item count: %d", len(tgt_items))
            logger.info("Source by type: %s", dict(src_counts))
            logger.info("Target by type: %s", dict(tgt_counts))
        else:
            logger.info("No source workspace set; skipping comparison.")

        # Section 7: API smoke checks (read-only)
        _print_header("API SMOKE TESTS (READ-ONLY)")
        workspace_details = target_workspace.endpoint.invoke(
            method="GET",
            url=f"{constants.DEFAULT_API_ROOT_URL}/v1/workspaces/{target_workspace.workspace_id}",
        )
        items_list = target_workspace.endpoint.invoke(
            method="GET",
            url=f"{constants.DEFAULT_API_ROOT_URL}/v1/workspaces/{target_workspace.workspace_id}/items",
        )
        if workspace_details["status_code"] != 200:
            raise RuntimeError(f"Workspace details call failed: {workspace_details}")
        if items_list["status_code"] != 200:
            raise RuntimeError(f"Workspace items call failed: {items_list}")
        logger.info("Workspace display name: %s", workspace_details["body"].get("displayName"))
        logger.info("Workspace item count: %d", len(items_list["body"].get("value", [])))

        # Section 8: Feature-flag safety test
        _print_header("FEATURE FLAG SAFETY TEST")
        try:
            publish_all_items(target_workspace, items_to_include=["Example.Notebook"])
            raise AssertionError("Expected InputError because feature flags are missing")
        except InputError as ex:
            logger.info("PASS feature-flag enforcement: %s", ex)

        # Section 9: Optional publish operation
        _print_header("OPTIONAL PUBLISH")
        if cfg["run_publish"]:
            logger.warning("RUN_PUBLISH=True -> publish will execute.")
            append_feature_flag(FeatureFlag.ENABLE_RESPONSE_COLLECTION.value)
            responses = publish_all_items(target_workspace)
            logger.info("Publish completed. Response collection present=%s", bool(responses))
            if responses:
                logger.info("Response keys: %s", list(responses.keys()))
        else:
            logger.info("RUN_PUBLISH is false. Skipping publish.")

        # Section 10: Optional unpublish operation
        _print_header("OPTIONAL UNPUBLISH")
        if cfg["run_unpublish"]:
            if not cfg["confirm_unpublish"]:
                raise RuntimeError(
                    "RUN_UNPUBLISH is true but CONFIRM_UNPUBLISH is not true. "
                    "Set CONFIRM_UNPUBLISH=true to acknowledge deletion risk."
                )
            logger.warning("RUN_UNPUBLISH=True + CONFIRM_UNPUBLISH=True -> unpublish will execute.")
            unpublish_all_orphan_items(target_workspace, item_name_exclude_regex="^$")
            logger.info("Unpublish completed.")
        else:
            logger.info("RUN_UNPUBLISH is false. Skipping unpublish.")

        _print_header("SCRIPT COMPLETED SUCCESSFULLY")
        logger.info("Log file written to %s", Path(LOG_FILE).resolve())
        return 0
    except Exception as ex:
        _print_header("SCRIPT FAILED")
        logger.error("Failure: %s: %s", type(ex).__name__, ex)
        logger.error(traceback.format_exc())
        logger.error("See log file: %s", Path(LOG_FILE).resolve())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
