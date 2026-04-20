"""Utilities for updating configlet content through the CloudVision API."""

import ssl

import certifi

from cloudvision.api.client import AsyncCVClient
from cloudvision.api.arista.configlet.v1 import (
    ConfigletServiceStub,
    ConfigletConfigServiceStub,
    ConfigletRequest,
    ConfigletKey,
    ConfigletConfig,
    ConfigletConfigSetRequest,
)


class ConfigletWriter:
    """Write configlet content into a CloudVision workspace.

    The writer handles the gRPC client setup and the read/write sequence needed
    to update a workspace-scoped copy of a configlet.
    """

    def __init__(self, token: str, cvp_host: str):
        """Store CloudVision connection details and prepare the TLS context."""
        self.token = token
        self.cvp_host = cvp_host

        # CloudVision uses gRPC over HTTP/2 with TLS, so the client needs a
        # trust store and ALPN configured before any requests are made.
        self.ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        self.ssl_ctx.set_alpn_protocols(["h2"])

    async def replace_configlet(
        self,
        configlet_id: str,
        workspace_id: str,
        content: str,
    ) -> dict[str, str]:
        """Replace a configlet's content inside the requested workspace.

        Args:
            configlet_id (str): Identifier of the configlet to update.
            workspace_id (str): Workspace that should receive the updated
                content.
            content (str): Full configlet body to store.

        Returns:
            dict[str, str]: Verification data read back from CloudVision after
            the write completes.
        """
        # Create a client for the lifetime of this operation so reads and writes
        # share the same authenticated channel configuration.
        client = AsyncCVClient(
            token=self.token,
            ssl_context=self.ssl_ctx,
            host=self.cvp_host,
            port=443,
        )

        with client as channel:
            read_stub = ConfigletServiceStub(channel)

            # Read the mainline version first so the workspace copy keeps the
            # existing display name and description.
            mainline_resp = await read_stub.get_one(
                ConfigletRequest(
                    key=ConfigletKey(
                        workspace_id="",
                        configlet_id=configlet_id,
                    )
                )
            )
            mainline_cfg = mainline_resp.value

            write_stub = ConfigletConfigServiceStub(channel)

            # Write the new body to the workspace-scoped version of the configlet.
            write_req = ConfigletConfigSetRequest(
                value=ConfigletConfig(
                    key=ConfigletKey(
                        workspace_id=workspace_id,
                        configlet_id=configlet_id,
                    ),
                    display_name=mainline_cfg.display_name,
                    description=mainline_cfg.description,
                    body=content,
                )
            )

            await write_stub.set(write_req)

            # Read the configlet back from the workspace so callers can confirm
            # the final stored state rather than assuming the write succeeded.
            verify_resp = await read_stub.get_one(
                ConfigletRequest(
                    key=ConfigletKey(
                        workspace_id=workspace_id,
                        configlet_id=configlet_id,
                    )
                )
            )

            return {
                "verified_display_name": verify_resp.value.display_name,
                "verified_body": verify_resp.value.body,
                "verified_workspace_id": verify_resp.value.key.workspace_id,
                "verified_configlet_id": verify_resp.value.key.configlet_id,
            }
