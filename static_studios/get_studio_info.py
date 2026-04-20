#!/usr/bin/env python3

import json
import config
from static_config_studio import StaticConfigStudioEditor

WORKSPACE_ID = ""

editor = StaticConfigStudioEditor(
    token=config.TOKEN,
    cvp_host=config.CVP_HOST,
    workspace_id=WORKSPACE_ID,
    studio_id=config.STATIC_CONFIG_STUDIO_ID,
)

inputs = editor.dump_inputs([])

configlets = editor.dump_inputs(["configlets"])

print(json.dumps(inputs, indent=2, sort_keys=True, default=str))

print("CONFIGLETS")
print(json.dumps(editor.dump_inputs(["configlets"]), indent=2, default=str))

print("ASSIGNMENTS")
print(json.dumps(editor.dump_inputs(["configletAssignments"]), indent=2, default=str))

print("ROOTS")
print(json.dumps(editor.dump_inputs(["configletAssignmentRoots"]), indent=2, default=str))
