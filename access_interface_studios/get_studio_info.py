#!/usr/bin/env python3

"""Dump the current state of the Access Interface Configuration Studio."""

import asyncio
import json
import sys
from pathlib import Path

from access_interface_studio import AccessInterfaceStudioEditor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspaces.workspace import create_ws


TOKEN = ""
CVP_HOST = "cvp.example.com"
WORKSPACE_NAME = "Access Interface Studio Info"
WORKSPACE_DESCRIPTION = "Temporary workspace for inspecting studio inputs"


async def main() -> None:
    """Create a workspace and print the full Studio input tree."""
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    editor = AccessInterfaceStudioEditor(
        token=TOKEN,
        cvp_host=CVP_HOST,
        workspace_id=workspace_id,
    )

    # Pull the full input tree first. This is the easiest way to learn the
    # Studio's current data model before targeting smaller subtrees.
    studio_inputs = editor.dump_inputs([])

    print(f"WORKSPACE_ID: {workspace_id}")
    print("FULL STUDIO INPUTS")
    print(json.dumps(studio_inputs, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    asyncio.run(main())
