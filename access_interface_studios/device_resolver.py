#!/usr/bin/env python3

"""Resolve CloudVision device identifiers from hostnames."""

import ssl

import certifi

from cloudvision.api.client import AsyncCVClient
from cloudvision.api.arista.inventory.v1 import DeviceServiceStub, DeviceStreamRequest


async def resolve_device_id(
    *,
    token: str,
    cvp_host: str,
    hostname: str,
) -> str:
    """Return the CloudVision device ID for an exact hostname match.

    Args:
        token (str): CloudVision API token.
        cvp_host (str): CloudVision host name.
        hostname (str): Exact hostname to search for.

    Returns:
        str: The matching CloudVision device ID.

    Raises:
        ValueError: If no device matches the hostname, or if multiple devices
            share the same hostname.
    """
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
        stub = DeviceServiceStub(channel)

        # Stream inventory devices and perform exact hostname matching locally.
        async for resp in stub.get_all(DeviceStreamRequest()):
            value = getattr(resp, "value", None)
            if value is None:
                continue

            device_hostname = getattr(value, "hostname", None) or getattr(
                value, "fqdn", None
            )
            if device_hostname != hostname:
                continue

            key = getattr(value, "key", None)
            device_id = getattr(key, "device_id", None) if key else None
            if device_id:
                matches.append(device_id)

    if not matches:
        raise ValueError(f"No device named {hostname!r} was found in CloudVision inventory.")

    unique_matches = sorted(set(matches))
    if len(unique_matches) > 1:
        raise ValueError(
            f"Multiple devices named {hostname!r} were found in CloudVision inventory: "
            f"{unique_matches}"
        )

    return unique_matches[0]
