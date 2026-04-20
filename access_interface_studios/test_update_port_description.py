#!/usr/bin/env python3

"""Minimal script for testing Access Interface Studio port description updates."""

import asyncio
import sys
from pathlib import Path

from access_interface_studio import AccessInterfaceStudioEditor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspaces.workspace import create_ws


WORKSPACE_NAME = "Access Interface Port Description Test"
WORKSPACE_DESCRIPTION = "Temporary workspace for testing port description updates"
HOSTNAME = "example-access-switch"
INTERFACE_NAME = "Ethernet1"
DESCRIPTION = "Updated by test_update_port_description.py"

TOKEN = ""
CVP_HOST = "cvp.example.com"

async def main() -> None:
    """Create a workspace and update a port description in the Studio."""
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    editor = AccessInterfaceStudioEditor(
        token=TOKEN,
        cvp_host=CVP_HOST,
        workspace_id=workspace_id,
    )

    result = await editor.set_port_description_for_hostname(
        hostname=HOSTNAME,
        interface_name=INTERFACE_NAME,
        description=DESCRIPTION,
    )

    print(f"Workspace ID: {workspace_id}")
    print(f"Operation: {result['operation']}")
    print(f"Hostname: {result['hostname']}")
    print(f"Device ID: {result['device_id']}")
    print(f"Interface: {result['interface_name']}")
    print(f"Description: {result['description']}")
    print(f"Query: {result['query']}")


if __name__ == "__main__":
    asyncio.run(main())
