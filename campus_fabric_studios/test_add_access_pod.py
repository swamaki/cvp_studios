#!/usr/bin/env python3

"""Minimal script for testing Campus Fabric access-pod creation."""

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from campus_fabric_studios.campus_fabric_studio import CampusFabricStudioEditor
from workspaces.workspace import create_ws


TOKEN = ""
CVP_HOST = "cvp.example.com"
WORKSPACE_NAME = "Campus Fabric Access Pod Test"
WORKSPACE_DESCRIPTION = "Temporary workspace for testing Campus Fabric access pod updates"
CAMPUS_NAME = "example-campus"
FABRIC_NAME = "example-fabric"
ACCESS_POD_NAME = "example-access-pod"
HOSTNAME = "example-leaf-switch"
NODE_ID = None

# Optional service membership. Leave both unset to create only the access pod.
SERVICE_VLAN_IDS = []
INCLUDE_IN_ALL_SERVICES = False


async def main() -> None:
    """Create a workspace and add one access pod to the selected fabric."""
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    editor = CampusFabricStudioEditor(
        token=TOKEN,
        cvp_host=CVP_HOST,
        workspace_id=workspace_id,
    )

    result = await editor.add_access_pod_for_hostname(
        campus_name=CAMPUS_NAME,
        fabric_name=FABRIC_NAME,
        access_pod_name=ACCESS_POD_NAME,
        hostname=HOSTNAME,
        node_id=NODE_ID,
        service_vlan_ids=SERVICE_VLAN_IDS,
        include_in_all_services=INCLUDE_IN_ALL_SERVICES,
    )

    print(f"Workspace ID: {workspace_id}")
    print(f"Operation: {result['operation']}")
    print(f"Campus: {result['campus_name']}")
    print(f"Fabric: {result['fabric_name']}")
    print(f"Access Pod: {result['access_pod_name']}")
    print(f"Hostname: {result['hostname']}")
    print(f"Device IDs: {result['device_ids']}")
    print(f"Node IDs: {result['node_ids']}")
    print(f"Service VLAN IDs: {result['attached_service_vlan_ids']}")


if __name__ == "__main__":
    asyncio.run(main())
