#!/usr/bin/env python3

"""Minimal script for testing batch interface updates in the Access Interface Studio."""

import asyncio
import sys
from pathlib import Path

from access_interface_studio import AccessInterfaceStudioEditor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspaces.workspace import create_ws


WORKSPACE_NAME = "Access Interface Batch Test"
WORKSPACE_DESCRIPTION = "Temporary workspace for testing batch interface updates"

UPDATES = {
    "example-access-switch-a": {
        "Ethernet1": {
            "description": "Batch update on example-access-switch-a Ethernet1",
            "port_profile": "ACCESS",
        },
        "Ethernet2": {
            "description": "Batch update on example-access-switch-a Ethernet49",
            "port_profile": "ACCESS",
        },
    },
    "example-access-switch-b": {
        "Ethernet11": {
            "description": "Batch update on example-access-switch-b Ethernet1",
            "port_profile": "ACCESS",
        },
        "Ethernet22": {
            "description": "Batch update on example-access-switch-b Ethernet49",
            "port_profile": "ACCESS",
        },
    },
}

TOKEN = ""
CVP_HOST = "cvp.example.com"



async def main() -> None:
    """Create a workspace and apply a batch of interface updates."""
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

    results = await editor.set_interfaces_for_hostnames(UPDATES)

    print(f"Workspace ID: {workspace_id}")
    for result in results:
        print("---")
        print(f"Operation: {result['operation']}")
        print(f"Hostname: {result['hostname']}")
        print(f"Device ID: {result['device_id']}")
        print(f"Interface: {result['interface_name']}")
        print(f"Description: {result['description']}")
        print(f"Port Profile: {result['port_profile']}")
        print(f"Query: {result['query']}")


if __name__ == "__main__":
    asyncio.run(main())
