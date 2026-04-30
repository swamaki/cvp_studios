#!/usr/bin/env python3

"""Helpers for reading and writing the Campus Fabric Studio."""

from copy import deepcopy
import certifi
import grpc
from typing import Any

from arista.tag.v2.services.gen_pb2_grpc import (
    TagAssignmentConfigServiceStub,
    TagConfigServiceStub,
)
from arista.tag.v2.services import gen_pb2 as tag_services
from arista.tag.v2.tag_pb2 import (
    ELEMENT_TYPE_DEVICE,
    TagAssignmentConfig,
    TagAssignmentKey,
    TagConfig,
    TagKey,
)
from arista.studio_topology.v1 import studio_topology_pb2 as studio_topology_models
from arista.studio_topology.v1.services import gen_pb2 as studio_topology_services
from arista.studio_topology.v1.services import gen_pb2_grpc as studio_topology_stubs
from access_interface_studios.device_resolver import resolve_device_id
from cloudvision.cvlib.studio import getStudioInputs, setStudioInput, setStudioInputs
from google.protobuf import wrappers_pb2 as pb


CAMPUS_FABRIC_STUDIO_ID = "studio-avd-campus-fabric"


class CampusFabricStudioEditor:
    """Read and update inputs for the Campus Fabric Studio."""

    def __init__(self, token: str, cvp_host: str, workspace_id: str):
        """Store connection details and prepare Studio gRPC credentials."""
        self.token = token
        self.cvp_host = cvp_host
        self.workspace_id = workspace_id
        self.studio_id = CAMPUS_FABRIC_STUDIO_ID

        with open(certifi.where(), "rb") as f:
            root_certs = f.read()

        tls_creds = grpc.ssl_channel_credentials(root_certificates=root_certs)
        token_creds = grpc.access_token_call_credentials(self.token)
        self.channel_creds = grpc.composite_channel_credentials(tls_creds, token_creds)
        self.target = f"{self.cvp_host}:443"

    def _client_getter(self, stub_cls):
        """Return a gRPC stub in the format expected by cvlib.studio."""
        channel = grpc.secure_channel(self.target, self.channel_creds)
        return stub_cls(channel)

    def dump_inputs(self, path=None):
        """Return Studio inputs at the requested path."""
        if path is None:
            path = []

        return getStudioInputs(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            path=path,
        )

    def set_input(self, input_path, value, remove=False):
        """Write a single Studio input value."""
        return setStudioInput(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            inputPath=input_path,
            value=value,
            remove=remove,
        )

    def set_inputs(self, updates):
        """Write multiple Studio input updates in one call."""
        return setStudioInputs(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            inputs=updates,
        )

    def list_fabrics(self) -> list[dict[str, Any]]:
        """Return a summary of campuses, fabrics, and access pods in the Studio."""
        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])
        campus_services = studio_inputs.get("campusServices", [])
        services_by_fabric_query = self._build_services_index(campus_services)
        fabrics = []

        for campus in campus_entries:
            campus_query = campus.get("tags", {}).get("query")
            campus_name = self._extract_name_from_query(campus_query, "Campus")

            campus_pods = campus.get("inputs", {}).get("campusDetails", {}).get("campusPod", [])
            for campus_pod in campus_pods:
                fabric_query = campus_pod.get("tags", {}).get("query")
                fabric_name = self._extract_name_from_query(fabric_query, "Campus-Pod")
                access_pod_names = [
                    self._extract_name_from_query(access_pod.get("tags", {}).get("query"), "Access-Pod")
                    for access_pod in campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", [])
                ]
                services = services_by_fabric_query.get(fabric_query, {})
                svis = services.get("svis", [])
                fabrics.append(
                    {
                        "campus_name": campus_name,
                        "campus_query": campus_query,
                        "fabric_name": fabric_name,
                        "fabric_query": fabric_query,
                        "access_pod_names": access_pod_names,
                        "existing_vlan_ids": [svi.get("id") for svi in svis],
                        "existing_vlan_count": len(svis),
                    }
                )

        return fabrics

    def create_fabric(
        self,
        campus_name: str,
        fabric_name: str,
        spine_device_ids: list[str],
        access_pod_defaults: dict[str, Any],
        campus_pod_routing_protocols: dict[str, Any],
        design: dict[str, Any],
        fabric_configurations: dict[str, Any],
        spine_defaults: dict[str, Any],
        spine_node_ids: list[int] | None = None,
        advanced_fabric_settings: dict[str, Any] | None = None,
        egress_connectivity: dict[str, Any] | None = None,
        node_type_properties: dict[str, Any] | None = None,
        third_party_devices: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new campus/fabric pair from explicit Studio input blocks."""
        if not spine_device_ids:
            raise ValueError("At least one spine device ID is required.")
        if len(set(spine_device_ids)) != len(spine_device_ids):
            raise ValueError("Duplicate spine device IDs were provided.")
        if spine_node_ids is not None:
            if len(spine_node_ids) != len(spine_device_ids):
                raise ValueError("spine_node_ids must match the number of spine_device_ids.")
            if len(set(spine_node_ids)) != len(spine_node_ids):
                raise ValueError("Duplicate spine node IDs were provided.")
        else:
            spine_node_ids = list(range(1, len(spine_device_ids) + 1))

        self._assign_devices_to_workspace(spine_device_ids)
        self._assign_device_tags_for_fabric(
            device_ids=spine_device_ids,
            campus_name=campus_name,
            fabric_name=fabric_name,
        )

        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])
        campus_services = studio_inputs.get("campusServices", [])

        existing_fabric = self._find_fabric_or_none(
            campus_entries,
            fabric_name=fabric_name,
            campus_name=campus_name,
        )
        if existing_fabric is not None:
            raise ValueError(
                f"Fabric {fabric_name!r} already exists under campus {campus_name!r}."
            )

        campus_entry = self._find_campus_entry(campus_entries, campus_name)
        if campus_entry is None:
            campus_entry = self._build_campus_entry(campus_name)
            campus_entries.append(campus_entry)

        campus_service_entry = self._find_campus_service_entry(campus_services, campus_name)
        if campus_service_entry is None:
            campus_service_entry = self._build_campus_services_entry(campus_name)
            campus_services.append(campus_service_entry)

        new_fabric = self._build_fabric_entry(
            fabric_name=fabric_name,
            spine_device_ids=spine_device_ids,
            spine_node_ids=spine_node_ids,
            access_pod_defaults=access_pod_defaults,
            campus_pod_routing_protocols=campus_pod_routing_protocols,
            design=design,
            fabric_configurations=fabric_configurations,
            spine_defaults=spine_defaults,
            advanced_fabric_settings=advanced_fabric_settings or {},
            egress_connectivity=egress_connectivity or {"externalDevices": []},
            node_type_properties=node_type_properties or {},
            third_party_devices=third_party_devices or [],
        )

        campus_entry.setdefault("inputs", {}).setdefault("campusDetails", {}).setdefault(
            "campusPod", []
        ).append(new_fabric)

        new_fabric_services = self._build_fabric_services_entry(
            fabric_name=fabric_name,
            campus_type=design["campusType"],
        )
        campus_service_entry.setdefault("inputs", {}).setdefault("campusServicesGroup", {}).setdefault(
            "campusPodsServices", []
        ).append(new_fabric_services)

        self.set_inputs(
            [
                (["campus"], campus_entries),
                (["campusServices"], campus_services),
            ]
        )
        return {
            "operation": "created",
            "campus_name": campus_name,
            "fabric_name": fabric_name,
            "spine_device_ids": spine_device_ids,
            "spine_node_ids": spine_node_ids,
            "campus_type": design["campusType"],
            "vxlan_overlay": design["vxlanOverlay"],
            "underlay_routing_protocol": campus_pod_routing_protocols["campusPodUnderlayRoutingProtocol"],
        }

    async def create_fabric_for_hostnames(
        self,
        campus_name: str,
        fabric_name: str,
        spine_hostnames: list[str],
        access_pod_defaults: dict[str, Any],
        campus_pod_routing_protocols: dict[str, Any],
        design: dict[str, Any],
        fabric_configurations: dict[str, Any],
        spine_defaults: dict[str, Any],
        spine_node_ids: list[int] | None = None,
        advanced_fabric_settings: dict[str, Any] | None = None,
        egress_connectivity: dict[str, Any] | None = None,
        node_type_properties: dict[str, Any] | None = None,
        third_party_devices: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Resolve spine hostnames to device IDs, then create a new fabric."""
        if not spine_hostnames:
            raise ValueError("At least one spine hostname is required.")
        if len(set(spine_hostnames)) != len(spine_hostnames):
            raise ValueError("Duplicate spine hostnames were provided.")

        spine_device_ids = []
        for hostname in spine_hostnames:
            try:
                spine_device_ids.append(
                    await resolve_device_id(
                        token=self.token,
                        cvp_host=self.cvp_host,
                        hostname=hostname,
                    )
                )
            except ValueError as exc:
                raise ValueError(
                    f"Failed to resolve spine hostname {hostname!r} for new fabric "
                    f"{fabric_name!r} in campus {campus_name!r}: {exc}"
                ) from exc

        result = self.create_fabric(
            campus_name=campus_name,
            fabric_name=fabric_name,
            spine_device_ids=spine_device_ids,
            access_pod_defaults=access_pod_defaults,
            campus_pod_routing_protocols=campus_pod_routing_protocols,
            design=design,
            fabric_configurations=fabric_configurations,
            spine_defaults=spine_defaults,
            spine_node_ids=spine_node_ids,
            advanced_fabric_settings=advanced_fabric_settings,
            egress_connectivity=egress_connectivity,
            node_type_properties=node_type_properties,
            third_party_devices=third_party_devices,
        )
        result["spine_hostnames"] = spine_hostnames
        return result

    def create_service_vlan(
        self,
        fabric_name: str,
        vlan_id: int,
        name: str,
        ip_virtual_router_subnet: str,
        campus_name: str | None = None,
        access_pod_names: list[str] | None = None,
        dhcp_servers: list[str] | None = None,
        vrf: str | None = None,
        routed: bool = True,
        eos_cli: str | None = None,
        underlay_multicast_enabled: str | None = None,
    ) -> dict[str, Any]:
        """Append a new VLAN service under the selected campus fabric."""
        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])
        campus_services = studio_inputs.get("campusServices", [])

        fabric = self._find_fabric(campus_entries, fabric_name, campus_name=campus_name)
        services_entry = self._find_services_entry(campus_services, fabric["fabric_query"])
        services = services_entry.setdefault("inputs", {}).setdefault("services", {})
        svis = services.setdefault("svis", [])

        existing_vlan = next((svi for svi in svis if svi.get("id") == vlan_id), None)
        if existing_vlan is not None:
            raise ValueError(
                f"VLAN {vlan_id} already exists in fabric {fabric_name!r} "
                f"with name {existing_vlan.get('name')!r}."
            )

        available_access_pods = fabric["access_pod_names"]
        if access_pod_names is None:
            access_pod_names = available_access_pods
        else:
            unknown_access_pods = sorted(set(access_pod_names) - set(available_access_pods))
            if unknown_access_pods:
                raise ValueError(
                    f"Unknown access pods for fabric {fabric_name!r}: {unknown_access_pods}. "
                    f"Available access pods: {available_access_pods}"
                )

        vlan_entry = self._build_service_vlan(
            vlan_id=vlan_id,
            name=name,
            ip_virtual_router_subnet=ip_virtual_router_subnet,
            access_pod_names=access_pod_names,
            dhcp_servers=dhcp_servers or [],
            vrf=vrf,
            routed=routed,
            eos_cli=eos_cli,
            underlay_multicast_enabled=underlay_multicast_enabled,
        )
        svis.append(vlan_entry)

        self.set_input(["campusServices"], campus_services)
        return {
            "operation": "created",
            "campus_name": fabric["campus_name"],
            "fabric_name": fabric["fabric_name"],
            "vlan_id": vlan_id,
            "name": name,
            "ip_virtual_router_subnet": ip_virtual_router_subnet,
            "access_pod_names": access_pod_names,
            "dhcp_servers": dhcp_servers or [],
            "vrf": vrf,
            "routed": routed,
        }

    def add_access_pod(
        self,
        fabric_name: str,
        access_pod_name: str,
        device_id: str,
        campus_name: str | None = None,
        node_id: int | None = None,
        service_vlan_ids: list[int] | None = None,
        include_in_all_services: bool = False,
    ) -> dict[str, Any]:
        """Create a single-leaf access pod and optionally attach it to services."""
        self._assign_devices_to_workspace([device_id])
        self._assign_device_tags_for_access_pod(
            device_ids=[device_id],
            campus_name=campus_name,
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
        )
        return self._add_access_pod_with_leaf_devices(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            leaf_devices=[
                {
                    "device_id": device_id,
                    "node_id": node_id,
                }
            ],
            campus_name=campus_name,
            service_vlan_ids=service_vlan_ids,
            include_in_all_services=include_in_all_services,
        )

    def add_mlag_access_pod(
        self,
        fabric_name: str,
        access_pod_name: str,
        primary_device_id: str,
        secondary_device_id: str,
        primary_node_id: int | None = None,
        secondary_node_id: int | None = None,
        campus_name: str | None = None,
        service_vlan_ids: list[int] | None = None,
        include_in_all_services: bool = False,
    ) -> dict[str, Any]:
        """Create a two-leaf access pod intended to operate as an MLAG pair."""
        if primary_device_id == secondary_device_id:
            raise ValueError("primary_device_id and secondary_device_id must be different.")
        if service_vlan_ids and include_in_all_services:
            raise ValueError(
                "Pass either service_vlan_ids or include_in_all_services, not both."
            )

        self._assign_devices_to_workspace([primary_device_id, secondary_device_id])
        self._assign_device_tags_for_access_pod(
            device_ids=[primary_device_id, secondary_device_id],
            campus_name=campus_name,
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
        )

        self._create_empty_access_pod(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            campus_name=campus_name,
        )
        primary_result = self._attach_leaf_to_access_pod(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            device_id=primary_device_id,
            campus_name=campus_name,
            node_id=primary_node_id,
        )
        secondary_result = self._attach_leaf_to_access_pod(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            device_id=secondary_device_id,
            campus_name=campus_name,
            node_id=secondary_node_id,
        )

        attached_service_vlan_ids = []
        if include_in_all_services or service_vlan_ids:
            studio_inputs = self.dump_inputs([])
            campus_entries = studio_inputs.get("campus", [])
            campus_services = studio_inputs.get("campusServices", [])
            fabric = self._find_fabric(campus_entries, fabric_name, campus_name=campus_name)
            services_entry = self._find_services_entry(campus_services, fabric["fabric_query"])
            services = services_entry.setdefault("inputs", {}).setdefault("services", {})
            svis = services.setdefault("svis", [])
            attached_service_vlan_ids = self._attach_access_pod_to_services(
                svis=svis,
                access_pod_name=access_pod_name,
                service_vlan_ids=service_vlan_ids,
                include_in_all_services=include_in_all_services,
            )
            self.set_input(["campusServices"], campus_services)

        return {
            "operation": "created",
            "campus_name": primary_result["campus_name"],
            "fabric_name": primary_result["fabric_name"],
            "access_pod_name": access_pod_name,
            "device_ids": [primary_device_id, secondary_device_id],
            "node_ids": primary_result["node_ids"] + secondary_result["node_ids"],
            "mlag": True,
            "attached_service_vlan_ids": attached_service_vlan_ids,
        }

    def _add_access_pod_with_leaf_devices(
        self,
        *,
        fabric_name: str,
        access_pod_name: str,
        leaf_devices: list[dict[str, Any]],
        campus_name: str | None,
        service_vlan_ids: list[int] | None,
        include_in_all_services: bool,
    ) -> dict[str, Any]:
        """Create an access pod from one or more leaf devices."""
        if service_vlan_ids and include_in_all_services:
            raise ValueError(
                "Pass either service_vlan_ids or include_in_all_services, not both."
            )
        if not leaf_devices:
            raise ValueError("At least one leaf device is required.")

        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])
        campus_services = studio_inputs.get("campusServices", [])

        fabric = self._find_fabric(campus_entries, fabric_name, campus_name=campus_name)
        campus_pod = self._find_campus_pod_entry(campus_entries, fabric["fabric_query"])
        access_pods = (
            campus_pod.setdefault("inputs", {})
            .setdefault("campusPodFacts", {})
            .setdefault("accessPods", [])
        )

        access_pod_query = f"Access-Pod:{access_pod_name}"

        existing_access_pod = next(
            (
                access_pod
                for access_pod in access_pods
                if access_pod.get("tags", {}).get("query") == access_pod_query
            ),
            None,
        )
        if existing_access_pod is not None:
            raise ValueError(
                f"Access pod {access_pod_name!r} already exists in fabric {fabric_name!r}."
            )

        existing_device_queries = {
            leaf.get("tags", {}).get("query"): access_pod.get("tags", {}).get("query")
            for access_pod in access_pods
            for leaf in access_pod.get("inputs", {}).get("accessPodFacts", {}).get("leafs", [])
        }
        leaf_nodes = []
        next_node_id = self._next_access_leaf_node_id(campus_pod)
        requested_node_ids = [
            leaf_device.get("node_id")
            for leaf_device in leaf_devices
            if leaf_device.get("node_id") is not None
        ]
        if len(requested_node_ids) != len(set(requested_node_ids)):
            raise ValueError("Duplicate node IDs were provided for this access pod.")

        assigned_node_ids = set()
        for leaf_device in leaf_devices:
            device_id = leaf_device["device_id"]
            device_query = f"device:{device_id}"
            existing_device_assignment = existing_device_queries.get(device_query)
            if existing_device_assignment is not None:
                raise ValueError(
                    f"Device {device_id!r} is already assigned under {existing_device_assignment!r}."
                )

            node_id = leaf_device.get("node_id")
            if node_id is None:
                while self._node_id_in_use(campus_pod, next_node_id) or next_node_id in assigned_node_ids:
                    next_node_id += 1
                node_id = next_node_id
                next_node_id += 1
            elif self._node_id_in_use(campus_pod, node_id) or node_id in assigned_node_ids:
                raise ValueError(f"Node ID {node_id} is already in use in fabric {fabric_name!r}.")

            assigned_node_ids.add(node_id)
            leaf_nodes.append(
                {
                    "inputs": {
                        "leafsInfo": {
                            "nodeId": node_id,
                        }
                    },
                    "tags": {
                        "query": device_query,
                    },
                }
            )

        access_pods.append(
            {
                "inputs": {
                    "accessPodFacts": {
                        "leafs": leaf_nodes,
                        "memberLeafMlagPairs": [],
                        "memberLeafs": [],
                        "nodeGroupAttributesList": [],
                    }
                },
                "tags": {
                    "query": access_pod_query,
                },
            }
        )

        attached_service_vlan_ids = []
        if include_in_all_services or service_vlan_ids:
            services_entry = self._find_services_entry(campus_services, fabric["fabric_query"])
            services = services_entry.setdefault("inputs", {}).setdefault("services", {})
            svis = services.setdefault("svis", [])
            attached_service_vlan_ids = self._attach_access_pod_to_services(
                svis=svis,
                access_pod_name=access_pod_name,
                service_vlan_ids=service_vlan_ids,
                include_in_all_services=include_in_all_services,
            )

        updates = [(["campus"], campus_entries)]
        if include_in_all_services or service_vlan_ids:
            updates.append((["campusServices"], campus_services))
        self.set_inputs(updates)

        return {
            "operation": "created",
            "campus_name": fabric["campus_name"],
            "fabric_name": fabric["fabric_name"],
            "access_pod_name": access_pod_name,
            "device_ids": [leaf_device["device_id"] for leaf_device in leaf_devices],
            "node_ids": [leaf_node["inputs"]["leafsInfo"]["nodeId"] for leaf_node in leaf_nodes],
            "mlag": len(leaf_devices) == 2,
            "attached_service_vlan_ids": attached_service_vlan_ids,
        }

    def _create_empty_access_pod(
        self,
        *,
        fabric_name: str,
        access_pod_name: str,
        campus_name: str | None,
    ) -> dict[str, Any]:
        """Create an empty access pod that can later have devices attached."""
        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])

        fabric = self._find_fabric(campus_entries, fabric_name, campus_name=campus_name)
        campus_pod = self._find_campus_pod_entry(campus_entries, fabric["fabric_query"])
        access_pods = (
            campus_pod.setdefault("inputs", {})
            .setdefault("campusPodFacts", {})
            .setdefault("accessPods", [])
        )

        access_pod_query = f"Access-Pod:{access_pod_name}"
        existing_access_pod = next(
            (
                access_pod
                for access_pod in access_pods
                if access_pod.get("tags", {}).get("query") == access_pod_query
            ),
            None,
        )
        if existing_access_pod is not None:
            raise ValueError(
                f"Access pod {access_pod_name!r} already exists in fabric {fabric_name!r}."
            )

        access_pods.append(
            {
                "inputs": {
                    "accessPodFacts": {
                        "leafs": [],
                        "memberLeafMlagPairs": [],
                        "memberLeafs": [],
                        "nodeGroupAttributesList": [],
                    }
                },
                "tags": {
                    "query": access_pod_query,
                },
            }
        )
        self.set_input(["campus"], campus_entries)
        return {
            "campus_name": fabric["campus_name"],
            "fabric_name": fabric["fabric_name"],
            "access_pod_name": access_pod_name,
        }

    def _attach_leaf_to_access_pod(
        self,
        *,
        fabric_name: str,
        access_pod_name: str,
        device_id: str,
        campus_name: str | None,
        node_id: int | None,
    ) -> dict[str, Any]:
        """Attach one leaf device to an existing access pod."""
        studio_inputs = self.dump_inputs([])
        campus_entries = studio_inputs.get("campus", [])

        fabric = self._find_fabric(campus_entries, fabric_name, campus_name=campus_name)
        campus_pod = self._find_campus_pod_entry(campus_entries, fabric["fabric_query"])
        access_pod = self._find_access_pod_entry(campus_pod, access_pod_name)
        access_pod_facts = access_pod.setdefault("inputs", {}).setdefault("accessPodFacts", {})
        leafs = access_pod_facts.setdefault("leafs", [])

        device_query = f"device:{device_id}"
        existing_device_assignment = self._find_existing_device_assignment(campus_pod, device_query)
        if existing_device_assignment is not None:
            raise ValueError(
                f"Device {device_id!r} is already assigned under {existing_device_assignment!r}."
            )

        existing_leaf = next(
            (leaf for leaf in leafs if leaf.get("tags", {}).get("query") == device_query),
            None,
        )
        if existing_leaf is not None:
            raise ValueError(
                f"Device {device_id!r} is already present in access pod {access_pod_name!r}."
            )

        if node_id is None:
            node_id = self._next_access_leaf_node_id(campus_pod)
            while any(
                leaf.get("inputs", {}).get("leafsInfo", {}).get("nodeId") == node_id
                for leaf in leafs
            ):
                node_id += 1
        elif self._node_id_in_use(campus_pod, node_id):
            raise ValueError(f"Node ID {node_id} is already in use in fabric {fabric_name!r}.")

        leafs.append(
            {
                "inputs": {
                    "leafsInfo": {
                        "nodeId": node_id,
                    }
                },
                "tags": {
                    "query": device_query,
                },
            }
        )
        self.set_input(["campus"], campus_entries)

        return {
            "operation": "updated",
            "campus_name": fabric["campus_name"],
            "fabric_name": fabric["fabric_name"],
            "access_pod_name": access_pod_name,
            "device_ids": [device_id],
            "node_ids": [node_id],
        }

    async def add_access_pod_for_hostname(
        self,
        fabric_name: str,
        access_pod_name: str,
        hostname: str,
        campus_name: str | None = None,
        node_id: int | None = None,
        service_vlan_ids: list[int] | None = None,
        include_in_all_services: bool = False,
    ) -> dict[str, Any]:
        """Resolve a hostname to a device ID, then create the access pod."""
        try:
            device_id = await resolve_device_id(
                token=self.token,
                cvp_host=self.cvp_host,
                hostname=hostname,
            )
        except ValueError as exc:
            raise ValueError(
                f"Failed to resolve access-pod hostname {hostname!r} for access pod "
                f"{access_pod_name!r} in fabric {fabric_name!r}: {exc}"
            ) from exc
        result = self.add_access_pod(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            device_id=device_id,
            campus_name=campus_name,
            node_id=node_id,
            service_vlan_ids=service_vlan_ids,
            include_in_all_services=include_in_all_services,
        )
        result["hostname"] = hostname
        return result

    async def add_mlag_access_pod_for_hostnames(
        self,
        fabric_name: str,
        access_pod_name: str,
        primary_hostname: str,
        secondary_hostname: str,
        primary_node_id: int | None = None,
        secondary_node_id: int | None = None,
        campus_name: str | None = None,
        service_vlan_ids: list[int] | None = None,
        include_in_all_services: bool = False,
    ) -> dict[str, Any]:
        """Resolve two hostnames to device IDs, then create a two-leaf access pod."""
        if primary_hostname == secondary_hostname:
            raise ValueError("primary_hostname and secondary_hostname must be different.")

        try:
            primary_device_id = await resolve_device_id(
                token=self.token,
                cvp_host=self.cvp_host,
                hostname=primary_hostname,
            )
        except ValueError as exc:
            raise ValueError(
                f"Failed to resolve primary MLAG hostname {primary_hostname!r} for "
                f"access pod {access_pod_name!r} in fabric {fabric_name!r}: {exc}"
            ) from exc
        try:
            secondary_device_id = await resolve_device_id(
                token=self.token,
                cvp_host=self.cvp_host,
                hostname=secondary_hostname,
            )
        except ValueError as exc:
            raise ValueError(
                f"Failed to resolve secondary MLAG hostname {secondary_hostname!r} for "
                f"access pod {access_pod_name!r} in fabric {fabric_name!r}: {exc}"
            ) from exc
        result = self.add_mlag_access_pod(
            fabric_name=fabric_name,
            access_pod_name=access_pod_name,
            primary_device_id=primary_device_id,
            secondary_device_id=secondary_device_id,
            primary_node_id=primary_node_id,
            secondary_node_id=secondary_node_id,
            campus_name=campus_name,
            service_vlan_ids=service_vlan_ids,
            include_in_all_services=include_in_all_services,
        )
        result["primary_hostname"] = primary_hostname
        result["secondary_hostname"] = secondary_hostname
        return result

    def _assign_devices_to_workspace(self, device_ids: list[str]) -> list[str]:
        """Assign devices to the workspace topology so the Studio can consume them."""
        unique_device_ids = []
        for device_id in device_ids:
            if device_id not in unique_device_ids:
                unique_device_ids.append(device_id)

        existing_device_ids = set(self._get_workspace_device_ids())
        missing_device_ids = [
            device_id for device_id in unique_device_ids if device_id not in existing_device_ids
        ]
        if not missing_device_ids:
            return unique_device_ids

        client = self._client_getter(studio_topology_stubs.DeviceInputConfigServiceStub)
        for device_id in missing_device_ids:
            request = studio_topology_services.DeviceInputConfigSetRequest(
                value=studio_topology_models.DeviceInputConfig(
                    key=studio_topology_models.DeviceKey(
                        workspace_id=pb.StringValue(value=self.workspace_id),
                        device_id=pb.StringValue(value=device_id),
                    ),
                    device_info=studio_topology_models.DeviceInfo(
                        device_id=pb.StringValue(value=device_id),
                    ),
                    is_expected_device=pb.BoolValue(value=False),
                )
            )
            client.Set(request)

        return unique_device_ids

    def _assign_device_tags_for_fabric(
        self,
        *,
        device_ids: list[str],
        campus_name: str,
        fabric_name: str,
    ) -> None:
        """Assign campus and fabric tags to the supplied devices."""
        tag_pairs = [
            ("Campus", campus_name),
            ("Campus-Pod", fabric_name),
        ]
        self._ensure_device_tags_exist(tag_pairs)
        self._assign_device_tags(
            device_ids=device_ids,
            tag_pairs=tag_pairs,
        )

    def _assign_device_tags_for_access_pod(
        self,
        *,
        device_ids: list[str],
        campus_name: str | None,
        fabric_name: str,
        access_pod_name: str,
    ) -> None:
        """Assign campus, fabric, and access-pod tags to access devices."""
        if campus_name is None:
            studio_inputs = self.dump_inputs([])
            fabric = self._find_fabric(
                studio_inputs.get("campus", []),
                fabric_name=fabric_name,
                campus_name=None,
            )
            campus_name = fabric["campus_name"]

        tag_pairs = [
            ("Campus", campus_name),
            ("Campus-Pod", fabric_name),
            ("Access-Pod", access_pod_name),
        ]
        self._ensure_device_tags_exist(tag_pairs)
        self._assign_device_tags(
            device_ids=device_ids,
            tag_pairs=tag_pairs,
        )

    def _ensure_device_tags_exist(self, tag_pairs: list[tuple[str, str]]) -> None:
        """Create device-tag definitions in the workspace if needed."""
        client = self._client_getter(TagConfigServiceStub)
        for label, value in tag_pairs:
            request = tag_services.TagConfigSetRequest(
                value=TagConfig(
                    key=TagKey(
                        workspace_id=pb.StringValue(value=self.workspace_id),
                        element_type=ELEMENT_TYPE_DEVICE,
                        label=pb.StringValue(value=label),
                        value=pb.StringValue(value=value),
                    )
                )
            )
            client.Set(request)

    def _assign_device_tags(
        self,
        *,
        device_ids: list[str],
        tag_pairs: list[tuple[str, str]],
    ) -> None:
        """Assign one or more device tags to one or more devices."""
        client = self._client_getter(TagAssignmentConfigServiceStub)
        for device_id in dict.fromkeys(device_ids):
            for label, value in tag_pairs:
                request = tag_services.TagAssignmentConfigSetRequest(
                    value=TagAssignmentConfig(
                        key=TagAssignmentKey(
                            workspace_id=pb.StringValue(value=self.workspace_id),
                            element_type=ELEMENT_TYPE_DEVICE,
                            label=pb.StringValue(value=label),
                            value=pb.StringValue(value=value),
                            device_id=pb.StringValue(value=device_id),
                        )
                    )
                )
                client.Set(request)

    def assign_devices_to_workspace(self, device_ids: list[str]) -> list[str]:
        """Public wrapper for assigning devices to the workspace topology."""
        return self._assign_devices_to_workspace(device_ids)

    async def assign_devices_to_workspace_for_hostnames(
        self,
        hostnames: list[str],
    ) -> list[str]:
        """Resolve hostnames and assign the matching devices to the workspace topology."""
        if not hostnames:
            raise ValueError("At least one hostname is required.")
        if len(set(hostnames)) != len(hostnames):
            raise ValueError("Duplicate hostnames were provided.")

        device_ids = []
        for hostname in hostnames:
            try:
                device_ids.append(
                    await resolve_device_id(
                        token=self.token,
                        cvp_host=self.cvp_host,
                        hostname=hostname,
                    )
                )
            except ValueError as exc:
                raise ValueError(
                    f"Failed to resolve hostname {hostname!r} for workspace device assignment: {exc}"
                ) from exc

        return self._assign_devices_to_workspace(device_ids)

    def _get_workspace_device_ids(self) -> list[str]:
        """Return device IDs already assigned to this workspace topology."""
        client = self._client_getter(studio_topology_stubs.DeviceInputConfigServiceStub)
        request = studio_topology_services.DeviceInputConfigStreamRequest(
            partial_eq_filter=[
                studio_topology_models.DeviceInputConfig(
                    key=studio_topology_models.DeviceKey(
                        workspace_id=pb.StringValue(value=self.workspace_id),
                    )
                )
            ]
        )
        device_ids = []
        for response in client.GetAll(request):
            value = getattr(response, "value", None)
            if value is None:
                continue
            key = getattr(value, "key", None)
            device_id = getattr(getattr(key, "device_id", None), "value", None) if key else None
            if device_id:
                device_ids.append(device_id)
        return device_ids

    def dump_workspace_device_inputs(self) -> list[dict[str, Any]]:
        """Return raw workspace topology device-input records."""
        client = self._client_getter(studio_topology_stubs.DeviceInputConfigServiceStub)
        request = studio_topology_services.DeviceInputConfigStreamRequest(
            partial_eq_filter=[
                studio_topology_models.DeviceInputConfig(
                    key=studio_topology_models.DeviceKey(
                        workspace_id=pb.StringValue(value=self.workspace_id),
                    )
                )
            ]
        )

        records = []
        for response in client.GetAll(request):
            value = getattr(response, "value", None)
            if value is None:
                continue

            key = getattr(value, "key", None)
            device_info = getattr(value, "device_info", None)
            records.append(
                {
                    "workspace_id": getattr(getattr(key, "workspace_id", None), "value", None)
                    if key
                    else None,
                    "device_id": getattr(getattr(key, "device_id", None), "value", None)
                    if key
                    else None,
                    "device_info_device_id": getattr(
                        getattr(device_info, "device_id", None), "value", None
                    )
                    if device_info
                    else None,
                    "hostname": getattr(getattr(device_info, "hostname", None), "value", None)
                    if device_info
                    else None,
                    "is_expected_device": getattr(
                        getattr(value, "is_expected_device", None), "value", None
                    ),
                    "remove": getattr(getattr(value, "remove", None), "value", None),
                }
            )
        return records

    @staticmethod
    def _build_services_index(campus_services) -> dict[str, dict[str, Any]]:
        """Return the services block keyed by fabric query."""
        services_by_fabric_query = {}
        for campus_service in campus_services:
            campus_pods_services = (
                campus_service.get("inputs", {})
                .get("campusServicesGroup", {})
                .get("campusPodsServices", [])
            )
            for fabric_service in campus_pods_services:
                fabric_query = fabric_service.get("tags", {}).get("query")
                if fabric_query:
                    services_by_fabric_query[fabric_query] = fabric_service.get("inputs", {}).get(
                        "services", {}
                    )
        return services_by_fabric_query

    @staticmethod
    def _extract_name_from_query(query: str | None, prefix: str) -> str | None:
        """Extract the logical name from a Studio tag query."""
        if not query or not query.startswith(f"{prefix}:"):
            return None
        return query.split(":", 1)[1]

    def _find_fabric(
        self,
        campus_entries,
        fabric_name: str,
        campus_name: str | None = None,
    ) -> dict[str, Any]:
        """Return the selected fabric and its access-pod names."""
        matching_fabrics = []
        for campus in campus_entries:
            current_campus_name = self._extract_name_from_query(
                campus.get("tags", {}).get("query"), "Campus"
            )
            if campus_name is not None and current_campus_name != campus_name:
                continue

            campus_pods = campus.get("inputs", {}).get("campusDetails", {}).get("campusPod", [])
            for campus_pod in campus_pods:
                current_fabric_name = self._extract_name_from_query(
                    campus_pod.get("tags", {}).get("query"), "Campus-Pod"
                )
                if current_fabric_name != fabric_name:
                    continue

                access_pod_names = [
                    self._extract_name_from_query(access_pod.get("tags", {}).get("query"), "Access-Pod")
                    for access_pod in campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", [])
                ]
                matching_fabrics.append(
                    {
                        "campus_name": current_campus_name,
                        "fabric_name": current_fabric_name,
                        "fabric_query": campus_pod.get("tags", {}).get("query"),
                        "access_pod_names": access_pod_names,
                    }
                )

        if len(matching_fabrics) == 1:
            return matching_fabrics[0]
        if not matching_fabrics:
            if campus_name is not None:
                raise ValueError(
                    f"Fabric {fabric_name!r} was not found under campus {campus_name!r}."
                )
            raise ValueError(f"Fabric {fabric_name!r} was not found in the current Studio inputs.")
        raise ValueError(
            f"Fabric name {fabric_name!r} is ambiguous across campuses. "
            "Pass campus_name to disambiguate before writing updates."
        )

    def _find_fabric_or_none(
        self,
        campus_entries,
        fabric_name: str,
        campus_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Return a fabric if present, otherwise None."""
        try:
            return self._find_fabric(
                campus_entries=campus_entries,
                fabric_name=fabric_name,
                campus_name=campus_name,
            )
        except ValueError:
            return None

    def _find_services_entry(self, campus_services, fabric_query: str):
        """Return the campusServices item that owns the selected fabric service list."""
        for campus_service in campus_services:
            campus_pods_services = (
                campus_service.get("inputs", {})
                .get("campusServicesGroup", {})
                .get("campusPodsServices", [])
            )
            for fabric_service in campus_pods_services:
                if fabric_service.get("tags", {}).get("query") == fabric_query:
                    return fabric_service

        raise ValueError(
            f"No campusServices entry was found for fabric query {fabric_query!r}."
        )

    @staticmethod
    def _build_spine_nodes(
        *,
        spine_device_ids: list[str],
        spine_node_ids: list[int],
    ) -> list[dict[str, Any]]:
        """Return the Studio spine list for the supplied devices and node IDs."""
        return [
            {
                "inputs": {
                    "spinesInfo": {
                        "nodeId": node_id,
                    }
                },
                "tags": {
                    "query": f"device:{device_id}",
                },
            }
            for device_id, node_id in zip(spine_device_ids, spine_node_ids)
        ]

    def _build_fabric_entry(
        self,
        *,
        fabric_name: str,
        spine_device_ids: list[str],
        spine_node_ids: list[int],
        access_pod_defaults: dict[str, Any],
        campus_pod_routing_protocols: dict[str, Any],
        design: dict[str, Any],
        fabric_configurations: dict[str, Any],
        spine_defaults: dict[str, Any],
        advanced_fabric_settings: dict[str, Any],
        egress_connectivity: dict[str, Any],
        node_type_properties: dict[str, Any],
        third_party_devices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return a fresh campus-pod entry from explicit inputs."""
        return {
            "inputs": {
                "campusPodFacts": {
                    "accessPodDefaults": deepcopy(access_pod_defaults),
                    "accessPods": [],
                    "advancedFabricSettings": deepcopy(advanced_fabric_settings),
                    "campusPodRoutingProtocols": deepcopy(campus_pod_routing_protocols),
                    "design": deepcopy(design),
                    "egressConnectivity": deepcopy(egress_connectivity),
                    "fabricConfigurations": deepcopy(fabric_configurations),
                    "nodeTypeProperties": deepcopy(node_type_properties),
                    "spineDefaults": deepcopy(spine_defaults),
                    "spines": self._build_spine_nodes(
                        spine_device_ids=spine_device_ids,
                        spine_node_ids=spine_node_ids,
                    ),
                    "thirdPartyDevices": deepcopy(third_party_devices),
                }
            },
            "tags": {
                "query": f"Campus-Pod:{fabric_name}",
            },
        }

    @staticmethod
    def _build_campus_entry(campus_name: str) -> dict[str, Any]:
        """Return a fresh campus entry."""
        return {
            "inputs": {
                "campusDetails": {
                    "campusPod": [],
                }
            },
            "tags": {
                "query": f"Campus:{campus_name}",
            },
        }

    @staticmethod
    def _build_campus_services_entry(campus_name: str) -> dict[str, Any]:
        """Return a fresh campusServices entry."""
        return {
            "inputs": {
                "campusServicesGroup": {
                    "campusPodsServices": [],
                }
            },
            "tags": {
                "query": f"Campus:{campus_name}",
            },
        }

    @staticmethod
    def _build_fabric_services_entry(*, fabric_name: str, campus_type: str) -> dict[str, Any]:
        """Return a fresh fabric service entry."""
        return {
            "inputs": {
                "services": {
                    "campusType": campus_type,
                    "svis": [],
                }
            },
            "tags": {
                "query": f"Campus-Pod:{fabric_name}",
            },
        }

    @staticmethod
    def _find_campus_entry(campus_entries, campus_name: str):
        """Return the campus entry for the selected campus name, if present."""
        campus_query = f"Campus:{campus_name}"
        for campus in campus_entries:
            if campus.get("tags", {}).get("query") == campus_query:
                return campus
        return None

    @staticmethod
    def _find_campus_service_entry(campus_services, campus_name: str):
        """Return the campusServices entry for the selected campus name, if present."""
        campus_query = f"Campus:{campus_name}"
        for campus_service in campus_services:
            if campus_service.get("tags", {}).get("query") == campus_query:
                return campus_service
        return None

    def _find_campus_pod_entry(self, campus_entries, fabric_query: str):
        """Return the campusPod entry for the selected fabric."""
        for campus in campus_entries:
            campus_pods = campus.get("inputs", {}).get("campusDetails", {}).get("campusPod", [])
            for campus_pod in campus_pods:
                if campus_pod.get("tags", {}).get("query") == fabric_query:
                    return campus_pod
        raise ValueError(f"No campus entry was found for fabric query {fabric_query!r}.")

    @staticmethod
    def _find_access_pod_entry(campus_pod, access_pod_name: str):
        """Return the access-pod entry for the selected access-pod name."""
        access_pod_query = f"Access-Pod:{access_pod_name}"
        access_pods = campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", [])
        for access_pod in access_pods:
            if access_pod.get("tags", {}).get("query") == access_pod_query:
                return access_pod
        raise ValueError(f"Access pod {access_pod_name!r} was not found in the selected fabric.")

    @staticmethod
    def _find_existing_device_assignment(campus_pod, device_query: str) -> str | None:
        """Return the existing access-pod query for a device assignment, if present."""
        access_pods = campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", [])
        for access_pod in access_pods:
            access_pod_query = access_pod.get("tags", {}).get("query")
            for leaf in access_pod.get("inputs", {}).get("accessPodFacts", {}).get("leafs", []):
                if leaf.get("tags", {}).get("query") == device_query:
                    return access_pod_query
        return None

    @staticmethod
    def _node_id_in_use(campus_pod, node_id: int) -> bool:
        """Return whether the node ID already exists anywhere in this fabric."""
        used_node_ids = set()
        used_node_ids.update(
            spine.get("inputs", {}).get("spinesInfo", {}).get("nodeId")
            for spine in campus_pod.get("inputs", {}).get("spineDefaults", {}).get("spines", [])
        )
        used_node_ids.update(
            spine.get("inputs", {}).get("spinesInfo", {}).get("nodeId")
            for spine in campus_pod.get("inputs", {}).get("spines", [])
        )
        for access_pod in campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", []):
            for leaf in access_pod.get("inputs", {}).get("accessPodFacts", {}).get("leafs", []):
                used_node_ids.add(leaf.get("inputs", {}).get("leafsInfo", {}).get("nodeId"))
        return node_id in used_node_ids

    def _next_access_leaf_node_id(self, campus_pod) -> int:
        """Return the next available node ID for a new access leaf."""
        used_node_ids = []
        for spine in campus_pod.get("inputs", {}).get("spines", []):
            node_id = spine.get("inputs", {}).get("spinesInfo", {}).get("nodeId")
            if node_id is not None:
                used_node_ids.append(node_id)
        for access_pod in campus_pod.get("inputs", {}).get("campusPodFacts", {}).get("accessPods", []):
            for leaf in access_pod.get("inputs", {}).get("accessPodFacts", {}).get("leafs", []):
                node_id = leaf.get("inputs", {}).get("leafsInfo", {}).get("nodeId")
                if node_id is not None:
                    used_node_ids.append(node_id)

        if not used_node_ids:
            return 1
        return max(used_node_ids) + 1

    @staticmethod
    def _attach_access_pod_to_services(
        *,
        svis,
        access_pod_name: str,
        service_vlan_ids: list[int] | None,
        include_in_all_services: bool,
    ) -> list[int]:
        """Append the access pod to selected service VLAN device lists."""
        target_vlans = set(service_vlan_ids or [])
        attached_service_vlan_ids = []
        access_pod_query = f"Access-Pod:{access_pod_name}"

        if target_vlans:
            existing_vlan_ids = {svi.get("id") for svi in svis}
            missing_vlan_ids = sorted(target_vlans - existing_vlan_ids)
            if missing_vlan_ids:
                raise ValueError(
                    f"Service VLAN IDs were not found in the current Studio inputs: {missing_vlan_ids}"
                )

        for svi in svis:
            vlan_id = svi.get("id")
            if not include_in_all_services and vlan_id not in target_vlans:
                continue

            devices = svi.setdefault("devices", [])
            already_present = any(
                device.get("tagQuery", {}).get("tags", {}).get("query") == access_pod_query
                for device in devices
            )
            if already_present:
                attached_service_vlan_ids.append(vlan_id)
                continue

            devices.append(
                {
                    "enabled": None,
                    "ipVirtualRouterSubnet": None,
                    "tagQuery": {
                        "tags": {
                            "query": access_pod_query,
                        }
                    },
                }
            )
            attached_service_vlan_ids.append(vlan_id)

        return attached_service_vlan_ids

    @staticmethod
    def _build_service_vlan(
        *,
        vlan_id: int,
        name: str,
        ip_virtual_router_subnet: str,
        access_pod_names: list[str],
        dhcp_servers: list[str],
        vrf: str | None,
        routed: bool,
        eos_cli: str | None,
        underlay_multicast_enabled: str | None,
    ) -> dict[str, Any]:
        """Return a service VLAN entry shaped like the current Studio dump."""
        vlan_entry = {
            "addressLocking": {},
            "devices": [
                {
                    "enabled": None,
                    "ipVirtualRouterSubnet": None,
                    "tagQuery": {
                        "tags": {
                            "query": f"Access-Pod:{access_pod_name}",
                        }
                    },
                }
                for access_pod_name in access_pod_names
            ],
            "dhcpHelpers": [
                {
                    "dhcpServer": dhcp_server,
                    "sourceInterface": None,
                    "sourceVrf": None,
                }
                for dhcp_server in dhcp_servers
            ],
            "enabled": None,
            "eosCli": eos_cli,
            "id": vlan_id,
            "ipVirtualRouterSubnet": ip_virtual_router_subnet,
            "multicast": {},
            "name": name,
            "nodes": [],
            "routed": routed,
            "vrf": vrf,
        }
        if underlay_multicast_enabled is not None:
            vlan_entry["multicast"] = {
                "underlayMulticastEnabled": underlay_multicast_enabled,
            }
        return vlan_entry
