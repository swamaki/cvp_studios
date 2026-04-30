#!/usr/bin/env python3

"""Minimal script for testing Campus Fabric service VLAN creation."""

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
WORKSPACE_NAME = "Campus Fabric Service VLAN Test"
WORKSPACE_DESCRIPTION = "Temporary workspace for testing Campus Fabric service VLAN updates"
CAMPUS_NAME = "example-campus"
FABRIC_NAME = "example-fabric"
VLAN_ID = 3999
VLAN_NAME = "TEST_VLAN"
IP_VIRTUAL_ROUTER_SUBNET = "10.139.99.0/24"
ACCESS_POD_NAMES = None
DHCP_SERVERS = ["192.0.2.10", "192.0.2.11"]
VRF = None
ROUTED = True
EOS_CLI = None
UNDERLAY_MULTICAST_ENABLED = None


async def main() -> None:
    """Create a workspace and add one service VLAN to the selected fabric."""
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

    result = editor.create_service_vlan(
        campus_name=CAMPUS_NAME,
        fabric_name=FABRIC_NAME,
        vlan_id=VLAN_ID,
        name=VLAN_NAME,
        ip_virtual_router_subnet=IP_VIRTUAL_ROUTER_SUBNET,
        access_pod_names=ACCESS_POD_NAMES,
        dhcp_servers=DHCP_SERVERS,
        vrf=VRF,
        routed=ROUTED,
        eos_cli=EOS_CLI,
        underlay_multicast_enabled=UNDERLAY_MULTICAST_ENABLED,
    )

    print(f"Workspace ID: {workspace_id}")
    print(f"Operation: {result['operation']}")
    print(f"Campus: {result['campus_name']}")
    print(f"Fabric: {result['fabric_name']}")
    print(f"VLAN ID: {result['vlan_id']}")
    print(f"Name: {result['name']}")
    print(f"Subnet: {result['ip_virtual_router_subnet']}")
    print(f"Access Pods: {result['access_pod_names']}")
    print(f"DHCP Servers: {result['dhcp_servers']}")


if __name__ == "__main__":
    asyncio.run(main())
