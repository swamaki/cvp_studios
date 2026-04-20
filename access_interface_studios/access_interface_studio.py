#!/usr/bin/env python3

"""Helpers for reading and writing the Access Interface Configuration Studio."""

import grpc
import certifi
from typing import Any, Mapping

from cloudvision.cvlib.studio import getStudioInputs, setStudioInput, setStudioInputs
from device_resolver import resolve_device_id


ACCESS_INTERFACE_STUDIO_ID = "studio-campus-access-interfaces"


class AccessInterfaceStudioEditor:
    """Read and update inputs for the Access Interface Configuration Studio."""

    def __init__(self, token: str, cvp_host: str, workspace_id: str):
        """Store connection details and prepare Studio gRPC credentials."""
        self.token = token
        self.cvp_host = cvp_host
        self.workspace_id = workspace_id
        self.studio_id = ACCESS_INTERFACE_STUDIO_ID

        # Build grpcio channel credentials using the system trust store and the
        # CloudVision token for authentication.
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

    def set_port_description(
        self,
        switch_name: str,
        interface_name: str,
        description: str,
    ) -> dict[str, str]:
        """Set the port description for a switch interface in this Studio."""
        result = self.set_interface_config(
            switch_name=switch_name,
            interface_name=interface_name,
            description=description,
        )
        return {
            "operation": result["operation"],
            "switch_name": result["switch_name"],
            "interface_name": result["interface_name"],
            "description": result["description"],
            "query": result["query"],
        }

    def set_interface_config(
        self,
        switch_name: str,
        interface_name: str,
        description: str | None = None,
        port_profile: str | None = None,
        access_pod_name: str | None = None,
    ) -> dict[str, str | None]:
        """Set interface fields for a switch interface in this Studio.

        The method updates an existing interface if it is already present in the
        Studio input tree. If the interface does not exist yet, it appends a new
        interface entry under the access pod that already contains other
        interfaces for the same switch.

        Args:
            switch_name (str): Switch identifier used by the Studio's interface
                query suffix.
            interface_name (str): Interface name, for example `Ethernet1`.
            description (str | None): Description text to store for the
                interface.
            port_profile (str | None): Port profile name to store for the
                interface.
            access_pod_name (str | None): Access pod name to use when the
                switch does not already have interfaces in the Studio.

        Returns:
            dict[str, str | None]: Summary of the update that was written.

        Raises:
            ValueError: If the switch cannot be mapped to exactly one access pod
                in the current Studio input tree, or if no fields were supplied
                to update.
        """
        if description is None and port_profile is None:
            raise ValueError("At least one of description or port_profile must be provided.")

        studio_inputs = self.dump_inputs([])
        campus_inputs = studio_inputs.get("campus", [])
        result = self._apply_interface_update(
            campus_inputs=campus_inputs,
            switch_name=switch_name,
            interface_name=interface_name,
            description=description,
            port_profile=port_profile,
            access_pod_name=access_pod_name,
        )

        # Write the updated campus tree back to the Studio.
        self.set_input(["campus"], campus_inputs)
        return result

    async def set_port_description_for_hostname(
        self,
        hostname: str,
        interface_name: str,
        description: str,
    ) -> dict[str, str]:
        """Resolve a hostname to a device ID, then update the port description."""
        device_id = await resolve_device_id(
            token=self.token,
            cvp_host=self.cvp_host,
            hostname=hostname,
        )

        result = self.set_interface_config(
            switch_name=device_id,
            interface_name=interface_name,
            description=description,
            access_pod_name=hostname,
        )
        result["hostname"] = hostname
        result["device_id"] = device_id
        return result

    async def set_interface_config_for_hostname(
        self,
        hostname: str,
        interface_name: str,
        description: str | None = None,
        port_profile: str | None = None,
    ) -> dict[str, str | None]:
        """Resolve a hostname to a device ID, then update interface fields."""
        device_id = await resolve_device_id(
            token=self.token,
            cvp_host=self.cvp_host,
            hostname=hostname,
        )

        result = self.set_interface_config(
            switch_name=device_id,
            interface_name=interface_name,
            description=description,
            port_profile=port_profile,
            access_pod_name=hostname,
        )
        result["hostname"] = hostname
        result["device_id"] = device_id
        return result

    async def set_interfaces_for_hostnames(
        self,
        updates: Mapping[str, Mapping[str, Mapping[str, Any]]],
    ) -> list[dict[str, str | None]]:
        """Update many interfaces on many switches in a single workspace write.

        Args:
            updates (Mapping[str, Mapping[str, Mapping[str, Any]]]): Nested
                mapping shaped like:
                {
                    "switch-a": {
                        "Ethernet1": {
                            "description": "Desk 12",
                            "port_profile": "ACCESS",
                        },
                        "Ethernet2": {
                            "port_profile": "PHONE",
                        },
                    },
                }

        Returns:
            list[dict[str, str | None]]: Per-interface summaries of the updates
            that were written.
        """
        studio_inputs = self.dump_inputs([])
        campus_inputs = studio_inputs.get("campus", [])
        results = []

        for hostname, interface_updates in updates.items():
            device_id = await resolve_device_id(
                token=self.token,
                cvp_host=self.cvp_host,
                hostname=hostname,
            )

            for interface_name, interface_fields in interface_updates.items():
                result = self._apply_interface_update(
                    campus_inputs=campus_inputs,
                    switch_name=device_id,
                    interface_name=interface_name,
                    description=interface_fields.get("description"),
                    port_profile=interface_fields.get("port_profile"),
                    access_pod_name=hostname,
                )
                result["hostname"] = hostname
                result["device_id"] = device_id
                results.append(result)

        # Apply all interface edits with one write so every change lands in the
        # same workspace state.
        self.set_input(["campus"], campus_inputs)
        return results

    def _apply_interface_update(
        self,
        campus_inputs,
        switch_name: str,
        interface_name: str,
        description: str | None = None,
        port_profile: str | None = None,
        access_pod_name: str | None = None,
    ) -> dict[str, str | None]:
        """Update or create a single interface entry inside the Studio tree."""
        if description is None and port_profile is None:
            raise ValueError("At least one of description or port_profile must be provided.")

        interface_query = self._build_interface_query(
            switch_name=switch_name,
            interface_name=interface_name,
        )

        exact_match = None
        switch_pod_candidates = []
        named_access_pod = None

        # Walk the campus tree and inspect every access pod's interface list.
        # The Studio stores interface assignments inside:
        # campus -> campusPod -> accessPod -> interfaces
        for access_pod in self._iter_access_pods(campus_inputs):
            if self._extract_access_pod_name(access_pod) == access_pod_name:
                named_access_pod = access_pod

            interfaces = access_pod.setdefault("inputs", {}).setdefault("interfaces", [])
            pod_has_switch = False

            for interface_data in interfaces:
                query = interface_data.get("tags", {}).get("query")
                if query == interface_query:
                    exact_match = access_pod, interface_data
                    break

                if self._extract_switch_identifier(query) == switch_name:
                    pod_has_switch = True

            if exact_match is not None:
                break

            if pod_has_switch:
                switch_pod_candidates.append(access_pod)

        operation = "updated"

        if exact_match is not None:
            _, interface_data = exact_match
            adapter_details = interface_data.setdefault("inputs", {}).setdefault(
                "adapterDetails", {}
            )
        else:
            target_access_pod = self._select_access_pod(
                switch_name=switch_name,
                candidates=switch_pod_candidates,
                named_access_pod=named_access_pod,
                access_pod_name=access_pod_name,
            )
            adapter_details = {}
            target_interfaces = target_access_pod.setdefault("inputs", {}).setdefault(
                "interfaces", []
            )
            target_interfaces.append(
                {
                    "inputs": {
                        "adapterDetails": adapter_details,
                    },
                    "tags": {
                        "query": interface_query,
                    },
                }
            )
            operation = "created"

        # Only overwrite the fields the caller provided.
        if description is not None:
            adapter_details["description"] = description
        if port_profile is not None:
            adapter_details["portProfile"] = port_profile

        return {
            "operation": operation,
            "switch_name": switch_name,
            "interface_name": interface_name,
            "description": description,
            "port_profile": port_profile,
            "query": interface_query,
        }

    @staticmethod
    def _build_interface_query(switch_name: str, interface_name: str) -> str:
        """Return the Studio query string for a switch interface."""
        return f"interface:{interface_name}@{switch_name}"

    @staticmethod
    def _extract_switch_identifier(query: str | None) -> str | None:
        """Extract the switch identifier from an interface query string."""
        if not query or "@" not in query:
            return None
        return query.rsplit("@", 1)[-1]

    @staticmethod
    def _extract_access_pod_name(access_pod) -> str | None:
        """Extract the access pod name from its tag query."""
        query = access_pod.get("tags", {}).get("query")
        if not query or not query.startswith("Access-Pod:"):
            return None
        return query.split(":", 1)[1]

    @staticmethod
    def _iter_access_pods(campus_inputs):
        """Yield every access pod object contained in the Studio input tree."""
        for campus in campus_inputs:
            campus_pods = campus.get("inputs", {}).get("campusPod", [])
            for campus_pod in campus_pods:
                access_pods = campus_pod.get("inputs", {}).get("accessPod", [])
                for access_pod in access_pods:
                    yield access_pod

    @staticmethod
    def _select_access_pod(
        switch_name: str,
        candidates,
        named_access_pod=None,
        access_pod_name: str | None = None,
    ):
        """Return the best access pod candidate for a switch."""
        if len(candidates) == 1:
            return candidates[0]

        if not candidates and named_access_pod is not None:
            return named_access_pod

        if not candidates:
            raise ValueError(
                f"Could not find an access pod for switch {switch_name!r}. "
                f"No existing interfaces were found and access pod {access_pod_name!r} "
                "was not present in the Studio."
            )

        raise ValueError(
            f"Found multiple access pods for switch {switch_name!r}. "
            "The switch must map to exactly one access pod before a new interface can be added."
        )
