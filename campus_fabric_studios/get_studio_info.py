#!/usr/bin/env python3

"""Dump the current state of the Campus Fabric Studio."""

import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from campus_fabric_studios.campus_fabric_studio import CampusFabricStudioEditor
from workspaces.workspace import create_ws



async def get_info(token, cvp_host, workspace_name, workspace_description):
    """Create a workspace and return the full Studio input tree."""
    workspace_id = await create_ws(
        token=token,
        cvp_host=cvp_host,
        display_name=workspace_name,
        description=workspace_description,
    )

    editor = CampusFabricStudioEditor(
        token=token,
        cvp_host=cvp_host,
        workspace_id=workspace_id,
    )

    studio_inputs = editor.dump_inputs([])
    return workspace_id, studio_inputs


async def main() -> None:
    """Create a workspace and print the full Studio input tree."""
    workspace_id, studio_inputs = await get_info(
        TOKEN,
        CVP_HOST,
        WORKSPACE_NAME,
        WORKSPACE_DESCRIPTION,
    )

    print(f"WORKSPACE_ID: {workspace_id}")
    print("FULL STUDIO INPUTS")
    print(json.dumps(studio_inputs, indent=2, sort_keys=True, default=str))


TOKEN = ""
CVP_HOST = "cvp.example.com"
WORKSPACE_NAME = "Campus Fabric Studio Info"
WORKSPACE_DESCRIPTION = "Temporary workspace for inspecting campus fabric studio inputs"


if __name__ == "__main__":
    asyncio.run(main())
