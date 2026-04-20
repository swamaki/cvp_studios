#!/usr/bin/env python3

"""Minimal script for testing configlet ID resolution and configlet writes."""

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configlet_writer import ConfigletWriter
from resolve_configlet_id import get_configlet_id
from workspaces.workspace import create_ws


TOKEN = ""
CVP_HOST = "cvp.example.com"
WORKSPACE_NAME = "Example Configlet Test Workspace"
WORKSPACE_DESCRIPTION = "Temporary workspace for testing configlet updates"
CONFIGLET_NAME = "example-configlet"
CONTENT = "hostname example-device"


async def main() -> None:
    """Create a workspace, resolve a configlet ID, and optionally write content."""
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    # Resolve the configlet from mainline, then use the new workspace for the
    # write test.
    configlet_id = await get_configlet_id(
        token=TOKEN,
        cvp_host=CVP_HOST,
        configlet_name=CONFIGLET_NAME,
        workspace_id="",
    )
    print(f"Resolved configlet_id: {configlet_id}")

    if CONTENT is None:
        print("No replacement content set. Resolve test completed.")
        return

    # If CONTENT is set, write it to the resolved configlet ID.
    writer = ConfigletWriter(token=TOKEN, cvp_host=CVP_HOST)
    result = await writer.replace_configlet(
        configlet_id=configlet_id,
        workspace_id=workspace_id,
        content=CONTENT,
    )

    print("Write complete.")
    print(f"Verified workspace_id: {result['verified_workspace_id']}")
    print(f"Verified configlet_id: {result['verified_configlet_id']}")
    print(f"Verified display_name: {result['verified_display_name']}")


if __name__ == "__main__":
    asyncio.run(main())
