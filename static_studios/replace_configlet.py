#!/usr/bin/env python3

"""Replace a configlet's contents in a CloudVision workspace."""

from .configlet_writer import ConfigletWriter


async def replace_configlet(
    *,
    token: str,
    cvp_host: str,
    workspace_id: str,
    configlet_id: str,
    content: str,
) -> dict[str, str]:
    """Write replacement content to a single configlet."""
    writer = ConfigletWriter(token=token, cvp_host=cvp_host)

    return await writer.replace_configlet(
        configlet_id=configlet_id,
        workspace_id=workspace_id,
        content=content,
    )
