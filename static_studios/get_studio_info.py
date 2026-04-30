#!/usr/bin/env python3

"""Dump the current state of a static-config Studio."""

import asyncio
import json
import sys
from pathlib import Path

from static_config_studio import StaticConfigStudioEditor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspaces.workspace import create_ws


TOKEN = ""
CVP_HOST = "cvp.example.com"
STUDIO_ID = "example-static-config-studio"
WORKSPACE_NAME = "Static Config Studio Info"
WORKSPACE_DESCRIPTION = "Temporary workspace for inspecting static config studio inputs"


async def main() -> None:
    """Create a workspace and print the full Studio input tree."""
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    editor = StaticConfigStudioEditor(
        token=TOKEN,
        cvp_host=CVP_HOST,
        workspace_id=workspace_id,
        studio_id=STUDIO_ID,
    )

    inputs = editor.dump_inputs([])
    print(f"WORKSPACE_ID: {workspace_id}")
    print(json.dumps(inputs, indent=2, sort_keys=True, default=str))

    print("CONFIGLETS")
    print(json.dumps(editor.dump_inputs(["configlets"]), indent=2, default=str))

    print("ASSIGNMENTS")
    print(json.dumps(editor.dump_inputs(["configletAssignments"]), indent=2, default=str))

    print("ROOTS")
    print(json.dumps(editor.dump_inputs(["configletAssignmentRoots"]), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
