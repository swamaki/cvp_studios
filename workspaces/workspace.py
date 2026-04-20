#!/usr/bin/env python3

import ssl
import uuid

import certifi

from cloudvision.api.client import AsyncCVClient
from cloudvision.api.arista.workspace.v1 import (
    WorkspaceConfigServiceStub,
    WorkspaceConfig,
    WorkspaceConfigSetRequest,
    WorkspaceKey,
)


async def create_ws(
    *,
    token: str,
    cvp_host: str,
    display_name: str,
    description: str,
) -> str:
    """Create a CloudVision workspace and return its workspace ID."""
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ssl_ctx.set_alpn_protocols(["h2"])

    client = AsyncCVClient(
        token=token,
        ssl_context=ssl_ctx,
        host=cvp_host,
        port=443,
    )

    workspace_id = str(uuid.uuid4())

    with client as channel:
        workspace_service = WorkspaceConfigServiceStub(channel)

        req = WorkspaceConfigSetRequest(
            value=WorkspaceConfig(
                key=WorkspaceKey(
                    workspace_id=workspace_id
                ),
                display_name=display_name,
                description=description,
            )
        )

        await workspace_service.set(req)

        print("Workspace created")
        print(f"workspace_id: {workspace_id}")

    return workspace_id
