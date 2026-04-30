#!/usr/bin/env python3

"""Example workflow for creating a new fabric and adding access pods."""

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

WORKSPACE_NAME = "Campus Fabric Creation Example"
WORKSPACE_DESCRIPTION = "Temporary workspace for creating a new fabric and access pods"

NEW_CAMPUS_NAME = "example-new-campus"
NEW_FABRIC_NAME = "example-new-fabric"
SPINE_HOSTNAMES = ["example-spine-a", "example-spine-b"]
SPINE_NODE_IDS = [1, 2]

ACCESS_POD_DEFAULTS = {
    "mlagDetails": {
        "mlagDomainId": "MLAG",
        "mlagIbgpOriginIncomplete": False,
        "mlagPeerIPv4Pool": "169.254.0.0/31",
        "mlagPeerVlan": 4094,
        "virtualRouterMacAddress": "00:1c:73:00:00:99",
    },
    "ospfDetails": {
        "ospfDefaults": "redistribute connected",
    },
    "routerIdPool": "172.16.0.0/24",
    "uplinkInterfaceDetails": {
        "leafUplinksEosCli": "vlan 1000\n  state active",
        "uplinkNativeVlan": 1000,
    },
    "uplinkIpv4Pool": "172.15.0.0/24",
    "vtepLoopbackIPv4Pool": "172.16.1.0/24",
}

CAMPUS_POD_ROUTING_PROTOCOLS = {
    "campusPodUnderlayRoutingProtocol": "eBGP",
}

DESIGN = {
    "campusType": "L2",
    "vxlanOverlay": False,
}

FABRIC_CONFIGURATIONS = {
    "inbandManagementDetails": {
        "accessPods": [],
        "inbandManagementGateway": "10.130.1.1",
        "inbandManagementSubnet": "10.130.1.0/24",
        "inbandManagementVlan": 1000,
        "ipHelperAddresses": [
            {"dhcpServer": "192.0.2.10"},
            {"dhcpServer": "192.0.2.11"},
        ],
    },
    "multicast": {
        "underlayMulticast": True,
    },
}

SPINE_DEFAULTS = {
    "bgpDetails": {
        "bgpAsns": "65130",
        "bgpDistance": {
            "externalRoutes": 20,
            "internalRoutes": 200,
            "localRoutes": 200,
        },
        "bgpGracefulRestart": {
            "enabled": True,
            "restartTime": 300,
        },
        "bgpUpdateWaitForConvergence": True,
        "bgpUpdateWaitInstall": True,
        "maximumPaths": {
            "bgpEcmp": 4,
            "bgpMaximumPaths": 4,
        },
    },
    "mlagDetails": {
        "mlagDomainId": "MLAG",
        "mlagIbgpOriginIncomplete": False,
        "mlagPeerIPv4Pool": "10.130.0.250/31",
        "mlagPeerL3IPv4Pool": "10.130.0.252/31",
        "mlagPeerL3Vlan": 4093,
        "mlagPeerVlan": 4094,
        "virtualRouterMacAddress": "00:1c:73:00:00:99",
    },
    "ospfDetails": {
        "ospfDefaults": "redistribute connected",
    },
    "routerIdPool": "10.130.0.2/31",
}

ADVANCED_FABRIC_SETTINGS = {}
EGRESS_CONNECTIVITY = {"externalDevices": []}
NODE_TYPE_PROPERTIES = {}
THIRD_PARTY_DEVICES = []

SINGLE_ACCESS_POD_NAME = "example-single-access-pod"
SINGLE_ACCESS_POD_HOSTNAME = "example-leaf-single"
SINGLE_ACCESS_POD_NODE_ID = 11

MLAG_ACCESS_POD_NAME = "example-mlag-access-pod"
MLAG_PRIMARY_HOSTNAME = "example-leaf-a"
MLAG_SECONDARY_HOSTNAME = "example-leaf-b"
MLAG_PRIMARY_NODE_ID = 21
MLAG_SECONDARY_NODE_ID = 22


async def main() -> None:
    """Create a workspace, create a new fabric, then add access pods."""
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

    fabric_result = await editor.create_fabric_for_hostnames(
        campus_name=NEW_CAMPUS_NAME,
        fabric_name=NEW_FABRIC_NAME,
        spine_hostnames=SPINE_HOSTNAMES,
        access_pod_defaults=ACCESS_POD_DEFAULTS,
        campus_pod_routing_protocols=CAMPUS_POD_ROUTING_PROTOCOLS,
        design=DESIGN,
        fabric_configurations=FABRIC_CONFIGURATIONS,
        spine_defaults=SPINE_DEFAULTS,
        spine_node_ids=SPINE_NODE_IDS,
        advanced_fabric_settings=ADVANCED_FABRIC_SETTINGS,
        egress_connectivity=EGRESS_CONNECTIVITY,
        node_type_properties=NODE_TYPE_PROPERTIES,
        third_party_devices=THIRD_PARTY_DEVICES,
    )

    single_pod_result = await editor.add_access_pod_for_hostname(
        campus_name=NEW_CAMPUS_NAME,
        fabric_name=NEW_FABRIC_NAME,
        access_pod_name=SINGLE_ACCESS_POD_NAME,
        hostname=SINGLE_ACCESS_POD_HOSTNAME,
        node_id=SINGLE_ACCESS_POD_NODE_ID,
    )

    mlag_pod_result = await editor.add_mlag_access_pod_for_hostnames(
        campus_name=NEW_CAMPUS_NAME,
        fabric_name=NEW_FABRIC_NAME,
        access_pod_name=MLAG_ACCESS_POD_NAME,
        primary_hostname=MLAG_PRIMARY_HOSTNAME,
        secondary_hostname=MLAG_SECONDARY_HOSTNAME,
        primary_node_id=MLAG_PRIMARY_NODE_ID,
        secondary_node_id=MLAG_SECONDARY_NODE_ID,
    )

    print(f"Workspace ID: {workspace_id}")
    print()
    print("NEW FABRIC")
    print(f"Operation: {fabric_result['operation']}")
    print(f"Campus: {fabric_result['campus_name']}")
    print(f"Fabric: {fabric_result['fabric_name']}")
    print(f"Spine Hostnames: {fabric_result['spine_hostnames']}")
    print(f"Spine Device IDs: {fabric_result['spine_device_ids']}")
    print(f"Spine Node IDs: {fabric_result['spine_node_ids']}")
    print(f"Campus Type: {fabric_result['campus_type']}")
    print(f"VXLAN Overlay: {fabric_result['vxlan_overlay']}")
    print(f"Underlay Routing: {fabric_result['underlay_routing_protocol']}")
    print()
    print("SINGLE-LEAF ACCESS POD")
    print(f"Access Pod: {single_pod_result['access_pod_name']}")
    print(f"Hostname: {single_pod_result['hostname']}")
    print(f"Device IDs: {single_pod_result['device_ids']}")
    print(f"Node IDs: {single_pod_result['node_ids']}")
    print()
    print("TWO-LEAF ACCESS POD")
    print(f"Access Pod: {mlag_pod_result['access_pod_name']}")
    print(f"Primary Hostname: {mlag_pod_result['primary_hostname']}")
    print(f"Secondary Hostname: {mlag_pod_result['secondary_hostname']}")
    print(f"Device IDs: {mlag_pod_result['device_ids']}")
    print(f"Node IDs: {mlag_pod_result['node_ids']}")


if __name__ == "__main__":
    asyncio.run(main())
