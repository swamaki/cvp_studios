#!/usr/bin/env python3

"""Example workflows for adding single-leaf and two-leaf access pods."""

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

WORKSPACE_NAME = "Campus Fabric Access Pod Example"
WORKSPACE_DESCRIPTION = "Temporary workspace for adding access pods"

CAMPUS_NAME = "example-campus"
FABRIC_NAME = "example-fabric"

SINGLE_ACCESS_POD_NAME = "example-single-access-pod"
SINGLE_HOSTNAME = "example-leaf-single"

MLAG_ACCESS_POD_NAME = "example-mlag-access-pod"
PRIMARY_HOSTNAME = "example-leaf-a"
SECONDARY_HOSTNAME = "example-leaf-b"

# Leave as None to auto-assign the next available node ID.
SINGLE_NODE_ID = None

# Leave as None to auto-assign the next available node IDs.
PRIMARY_NODE_ID = None
SECONDARY_NODE_ID = None

# Optional service membership for the single-leaf access pod.
SINGLE_SERVICE_VLAN_IDS = []
SINGLE_INCLUDE_IN_ALL_SERVICES = False

# Optional service membership for the two-leaf access pod.
MLAG_SERVICE_VLAN_IDS = []
MLAG_INCLUDE_IN_ALL_SERVICES = False


async def main() -> None:
    """Create a workspace and append single-leaf and two-leaf access pods."""
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

    single_result = await editor.add_access_pod_for_hostname(
        campus_name=CAMPUS_NAME,
        fabric_name=FABRIC_NAME,
        access_pod_name=SINGLE_ACCESS_POD_NAME,
        hostname=SINGLE_HOSTNAME,
        node_id=SINGLE_NODE_ID,
        service_vlan_ids=SINGLE_SERVICE_VLAN_IDS,
        include_in_all_services=SINGLE_INCLUDE_IN_ALL_SERVICES,
    )

    mlag_result = await editor.add_mlag_access_pod_for_hostnames(
        campus_name=CAMPUS_NAME,
        fabric_name=FABRIC_NAME,
        access_pod_name=MLAG_ACCESS_POD_NAME,
        primary_hostname=PRIMARY_HOSTNAME,
        secondary_hostname=SECONDARY_HOSTNAME,
        primary_node_id=PRIMARY_NODE_ID,
        secondary_node_id=SECONDARY_NODE_ID,
        service_vlan_ids=MLAG_SERVICE_VLAN_IDS,
        include_in_all_services=MLAG_INCLUDE_IN_ALL_SERVICES,
    )

    print(f"Workspace ID: {workspace_id}")
    print()
    print("SINGLE-LEAF ACCESS POD")
    print(f"Operation: {single_result['operation']}")
    print(f"Campus: {single_result['campus_name']}")
    print(f"Fabric: {single_result['fabric_name']}")
    print(f"Access Pod: {single_result['access_pod_name']}")
    print(f"Hostname: {single_result['hostname']}")
    print(f"Device IDs: {single_result['device_ids']}")
    print(f"Node IDs: {single_result['node_ids']}")
    print(f"Service VLAN IDs: {single_result['attached_service_vlan_ids']}")
    print()
    print("TWO-LEAF ACCESS POD")
    print(f"Operation: {mlag_result['operation']}")
    print(f"Campus: {mlag_result['campus_name']}")
    print(f"Fabric: {mlag_result['fabric_name']}")
    print(f"Access Pod: {mlag_result['access_pod_name']}")
    print(f"Primary Hostname: {mlag_result['primary_hostname']}")
    print(f"Secondary Hostname: {mlag_result['secondary_hostname']}")
    print(f"Device IDs: {mlag_result['device_ids']}")
    print(f"Node IDs: {mlag_result['node_ids']}")
    print(f"Service VLAN IDs: {mlag_result['attached_service_vlan_ids']}")


if __name__ == "__main__":
    asyncio.run(main())
