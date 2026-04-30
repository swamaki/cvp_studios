#!/usr/bin/env python3

"""Example workflow for creating a workspace and updating configlets.

This script is meant to be read and edited by someone new to the project.
It demonstrates the three core steps:

1. Create a workspace in CloudVision.
2. Resolve one or more configlet IDs from their display names.
3. Write new content to those configlets inside the new workspace.

Fill in the variables below, then run the script from the project root with:

    python3 examples/example_configlet_workflow.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from static_studios.configlet_writer import ConfigletWriter
from static_studios.resolve_configlet_id import get_configlet_id
from workspaces.workspace import create_ws


# CloudVision connection details.
# Replace these values with your environment before running the script.
TOKEN = ""
CVP_HOST = "cvp.example.com"

# The workspace created by this script will use these values.
# Pick a name and description that make it obvious this workspace came from
# your automation or test run.
WORKSPACE_NAME = "Example Workspace"
WORKSPACE_DESCRIPTION = "Workspace created by examples/example_configlet_workflow.py"

# Each item below represents one configlet to update.
# "name" must exactly match the configlet's display name in CloudVision.
# "content" is the full replacement body that should be stored in the
# workspace copy of that configlet.
#
# Add more entries if you want to update multiple configlets in one run.
CONFIGLETS_TO_UPDATE = [
    {
        "name": "example-configlet",
        "content": """!
hostname example-switch
!
""",
    },
]


async def main() -> None:
    """Run the example workflow from workspace creation through configlet write."""
    # Step 1:
    # Create a new workspace. The returned workspace ID is what all later writes
    # will target.
    workspace_id = await create_ws(
        token=TOKEN,
        cvp_host=CVP_HOST,
        display_name=WORKSPACE_NAME,
        description=WORKSPACE_DESCRIPTION,
    )

    print(f"Created workspace: {workspace_id}")

    # Create the writer once and reuse it for each configlet update.
    writer = ConfigletWriter(token=TOKEN, cvp_host=CVP_HOST)

    # Step 2 and Step 3:
    # For each configlet name, resolve its ID from mainline and then write the
    # replacement content into the new workspace.
    for item in CONFIGLETS_TO_UPDATE:
        configlet_name = item["name"]
        replacement_content = item["content"]

        # Configlet lookup happens against mainline here, so workspace_id is an
        # empty string. This finds the base configlet by its display name.
        configlet_id = await get_configlet_id(
            token=TOKEN,
            cvp_host=CVP_HOST,
            configlet_name=configlet_name,
            workspace_id="",
        )

        print(f"Resolved {configlet_name!r} to configlet_id={configlet_id}")

        # Write the new configlet body into the workspace copy.
        result = await writer.replace_configlet(
            configlet_id=configlet_id,
            workspace_id=workspace_id,
            content=replacement_content,
        )

        # Print the verification data returned after the write.
        print(f"Updated configlet: {result['verified_display_name']}")
        print(f"Verified workspace_id: {result['verified_workspace_id']}")
        print(f"Verified configlet_id: {result['verified_configlet_id']}")


if __name__ == "__main__":
    asyncio.run(main())
