#!/usr/bin/env python3

"""Look up CloudVision configlet IDs by display name."""

import ssl

import certifi

from cloudvision.api.client import AsyncCVClient
from cloudvision.api.arista.configlet.v1 import (
    Configlet,
    ConfigletKey,
    ConfigletServiceStub,
    ConfigletStreamRequest,
)


async def get_configlet_id(
    *,
    token: str,
    cvp_host: str,
    configlet_name: str,
    workspace_id: str = "",
) -> str:
    """Return the configlet ID for an exact configlet name match.

    Args:
        token (str): CloudVision API token.
        cvp_host (str): CloudVision host, such as `www.arista.io`.
        configlet_name (str): Exact configlet display name to search for.
        workspace_id (str): Workspace to search. Leave empty to search mainline.

    Returns:
        str: The matching configlet ID.

    Raises:
        ValueError: If no configlet matches the requested name, or if multiple
            configlets share that exact name in the requested workspace.
    """
    # CloudVision uses gRPC over TLS with HTTP/2, so the client needs both a
    # trusted CA bundle and ALPN configured before opening the channel.
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ssl_ctx.set_alpn_protocols(["h2"])

    client = AsyncCVClient(
        token=token,
        ssl_context=ssl_ctx,
        host=cvp_host,
        port=443,
    )

    matches = []

    with client as channel:
        stub = ConfigletServiceStub(channel)

        # Scope the stream to a single workspace, then filter by exact display
        # name in Python so the lookup behavior is explicit.
        stream_req = ConfigletStreamRequest(
            partial_eq_filter=[
                Configlet(
                    key=ConfigletKey(workspace_id=workspace_id),
                )
            ]
        )

        async for resp in stub.get_all(stream_req):
            value = getattr(resp, "value", None)
            if value is None:
                continue

            display_name = getattr(value, "display_name", None) or getattr(
                value, "displayName", None
            )
            if display_name != configlet_name:
                continue

            key = getattr(value, "key", None)
            configlet_id = getattr(key, "configlet_id", None) if key else None
            if configlet_id:
                matches.append(configlet_id)

    if not matches:
        raise ValueError(
            f"No configlet named {configlet_name!r} was found in workspace {workspace_id!r}."
        )

    unique_matches = sorted(set(matches))
    if len(unique_matches) > 1:
        raise ValueError(
            f"Multiple configlets named {configlet_name!r} were found in workspace "
            f"{workspace_id!r}: {unique_matches}"
        )

    return unique_matches[0]
