#!/usr/bin/env python3

"""Example workflow for updating access interfaces in one workspace write."""

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACCESS_INTERFACE_DIR = PROJECT_ROOT / "access_interface_studios"

for import_path in (PROJECT_ROOT, ACCESS_INTERFACE_DIR):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

from access_interface_studio import AccessInterfaceStudioEditor
from workspaces.workspace import create_ws


TOKEN = ""
CVP_HOST = "cvp.example.com"

WORKSPACE_NAME = "Access Interface Example"
WORKSPACE_DESCRIPTION = "Temporary workspace for updating access interfaces"

INTERFACE_UPDATES = [
    {
        "hostname": "example-access-switch-a",
        "access_pod_name": "example-access-pod-a",
        "interfaces": [
            {
                "name": "Ethernet1",
                "description": "Example user port",
                "port_profile": "ACCESS",
            },
            {
                "name": "Ethernet2",
                "description": "Example phone port",
                "port_profile": "VOICE",
            },
        ],
    },
    {
        "hostname": "example-access-switch-b",
        "access_pod_name": "example-access-pod-b",
        "interfaces": [
            {
                "name": "Ethernet11",
                "description": "Example wireless access point",
                "port_profile": "AP",
            },
            {
                "name": "Ethernet12",
                "description": "Disabled spare port",
                "port_profile": "OFF",
            },
        ],
    },
]


async def main() -> None:
    """Create a workspace and apply the example interface updates."""
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

    results = await editor.set_interface_configs_for_updates(INTERFACE_UPDATES)

    print(f"Workspace ID: {workspace_id}")
    for result in results:
        print("---")
        print(f"Operation: {result['operation']}")
        print(f"Hostname: {result['hostname']}")
        print(f"Access Pod: {result['access_pod_name']}")
        print(f"Device ID: {result['device_id']}")
        print(f"Interface: {result['interface_name']}")
        print(f"Description: {result['description']}")
        print(f"Port Profile: {result['port_profile']}")
        print(f"Query: {result['query']}")


if __name__ == "__main__":
    asyncio.run(main())
