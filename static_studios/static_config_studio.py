#!/usr/bin/env python3

import grpc
import certifi

from cloudvision.cvlib.studio import getStudioInputs, setStudioInput, setStudioInputs


class StaticConfigStudioEditor:
    def __init__(self, token: str, cvp_host: str, workspace_id: str, studio_id: str):
        self.token = token
        self.cvp_host = cvp_host
        self.workspace_id = workspace_id
        self.studio_id = studio_id

        # Build grpcio channel credentials:
        # TLS trust + bearer token auth
        with open(certifi.where(), "rb") as f:
            root_certs = f.read()

        tls_creds = grpc.ssl_channel_credentials(root_certificates=root_certs)
        token_creds = grpc.access_token_call_credentials(self.token)
        self.channel_creds = grpc.composite_channel_credentials(tls_creds, token_creds)

        self.target = f"{self.cvp_host}:443"

    def _client_getter(self, stub_cls):
        """
        cvlib.studio expects a function that returns a grpcio stub.
        """
        channel = grpc.secure_channel(self.target, self.channel_creds)
        return stub_cls(channel)

    def dump_inputs(self, path=None):
        if path is None:
            path = []

        return getStudioInputs(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            path=path,
        )

    def set_input(self, input_path, value, remove=False):
        return setStudioInput(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            inputPath=input_path,
            value=value,
            remove=remove,
        )

    def set_inputs(self, updates):
        """
        updates = [
            (["some", "path"], value),
            (["another", "path"], value, True),  # remove=True
        ]
        """
        return setStudioInputs(
            self._client_getter,
            studioId=self.studio_id,
            workspaceId=self.workspace_id,
            inputs=updates,
        )
