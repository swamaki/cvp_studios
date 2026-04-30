# CVP Studio Tools

Basic Python helpers for working with Arista CloudVision and CloudVision Studios.

This repo is currently aimed at small, direct automation tasks rather than being a polished library. The main things it supports today are:

- Creating a CloudVision workspace
- Looking up a configlet ID by display name
- Replacing configlet contents inside a workspace
- Reading and updating the Access Interface Configuration Studio
- Reading the Campus Fabric Studio input tree

## Requirements

- Python 3.10+ recommended
- Access to an Arista CloudVision instance
- A CloudVision API token with permission to read inventory/configlets and write workspaces or Studio inputs

## Install

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How Configuration Works

There is no shared config file yet.

The scripts in this repo currently expect you to edit the file you want to run and set:

- `TOKEN`
- `CVP_HOST`
- Any workflow-specific values such as workspace name, configlet name, interface name, or replacement content

Example:

```python
TOKEN = "your-cloudvision-token"
CVP_HOST = "cvp.example.com"
```

## Quick Start

The simplest place to start is [example_configlet_workflow.py](./examples/example_configlet_workflow.py).

It shows the full flow for:

1. Creating a new workspace
2. Resolving a configlet ID from its display name
3. Writing replacement configlet content into that workspace

After filling in the values near the top of the file, run:

```bash
python3 examples/example_configlet_workflow.py
```

## Repo Layout

`workspaces/`

- Workspace creation helper

`examples/`

- End-to-end example scripts that can run directly from the `examples/` directory

`static_studios/`

- Configlet lookup and configlet update helpers
- Example/test scripts for configlet workflows

`access_interface_studios/`

- Helpers for reading and updating the Access Interface Configuration Studio
- Example/test scripts for port description and batch interface updates

`campus_fabric_studios/`

- Helpers for reading and updating the Campus Fabric Studio
- Script for dumping the current Campus Fabric Studio input tree
- Script for dumping workspace topology device assignments
- Example script for adding a service VLAN to a fabric
- Example script for adding an access pod to a fabric
- Example script for adding single-leaf and two-leaf access pods to a fabric
- Example script for creating a new fabric and adding access pods

## Common Workflows

### 1. Update a configlet in a new workspace

Recommended script:

- [example_configlet_workflow.py](./examples/example_configlet_workflow.py)

Alternative minimal test script:

- [static_studios/test_configlet_workflow.py](./static_studios/test_configlet_workflow.py)

What you edit:

- CloudVision token and host
- Workspace name/description
- Configlet display name
- Full replacement configlet body

### 2. Inspect Access Interface Studio inputs

Script:

- [access_interface_studios/get_studio_info.py](./access_interface_studios/get_studio_info.py)

This creates a workspace, reads the current Studio input tree, and prints it as JSON. It is useful when you want to understand the current Studio structure before writing updates.

Run with:

```bash
python3 access_interface_studios/get_studio_info.py
```

### 3. Update one interface description in Access Interface Studio

Script:

- [access_interface_studios/test_update_port_description.py](./access_interface_studios/test_update_port_description.py)
- [example_access_interface_workflow.py](./examples/example_access_interface_workflow.py)

What you edit:

- `TOKEN`
- `CVP_HOST`
- `HOSTNAME`
- `INTERFACE_NAME`
- `DESCRIPTION`

Run with:

```bash
python3 access_interface_studios/test_update_port_description.py
```

### 4. Update multiple interfaces in one workspace write

Script:

- [access_interface_studios/test_update_interfaces_batch.py](./access_interface_studios/test_update_interfaces_batch.py)
- [example_access_interface_workflow.py](./examples/example_access_interface_workflow.py)

Edit the `UPDATES` dictionary to define interface descriptions and/or port profiles by hostname.

Run with:

```bash
python3 access_interface_studios/test_update_interfaces_batch.py
```

### 5. Inspect Campus Fabric Studio inputs

Script:

- [campus_fabric_studios/get_studio_info.py](./campus_fabric_studios/get_studio_info.py)

This creates a workspace, reads the current input tree from
`studio-avd-campus-fabric`, and prints it as JSON so you can map the Studio
before making changes.

Run with:

```bash
python3 campus_fabric_studios/get_studio_info.py
```

### 6. Add a service VLAN to Campus Fabric Studio

Script:

- [campus_fabric_studios/test_add_service_vlan.py](./campus_fabric_studios/test_add_service_vlan.py)

This creates a workspace, targets a campus fabric by campus and fabric name, and
appends a new VLAN under the fabric's `services -> svis` list.

Edit:

- `TOKEN`
- `CVP_HOST`
- `CAMPUS_NAME`
- `FABRIC_NAME`
- `VLAN_ID`
- `VLAN_NAME`
- `IP_VIRTUAL_ROUTER_SUBNET`
- Optional `ACCESS_POD_NAMES`, `DHCP_SERVERS`, `VRF`, `EOS_CLI`

Run with:

```bash
python3 campus_fabric_studios/test_add_service_vlan.py
```

### 7. Add an access pod to Campus Fabric Studio

Script:

- [campus_fabric_studios/test_add_access_pod.py](./campus_fabric_studios/test_add_access_pod.py)

This creates a workspace, resolves a switch hostname to a CloudVision device ID,
creates a new single-leaf access pod under the selected campus fabric, and can
optionally attach that access pod to existing service VLANs.

Edit:

- `TOKEN`
- `CVP_HOST`
- `CAMPUS_NAME`
- `FABRIC_NAME`
- `ACCESS_POD_NAME`
- `HOSTNAME`
- Optional `NODE_ID`
- Optional `SERVICE_VLAN_IDS` or `INCLUDE_IN_ALL_SERVICES`

Run with:

```bash
python3 campus_fabric_studios/test_add_access_pod.py
```

## Notes

- These scripts create CloudVision workspaces but do not submit or approve changes for you.
- Configlet lookup uses exact display-name matching.
- Device lookup for Studio workflows uses exact hostname matching.
- The Access Interface Studio helper is written specifically for the `studio-campus-access-interfaces` Studio.
- The Campus Fabric Studio helper is written specifically for the `studio-avd-campus-fabric` Studio.

## Current Limitations

- No CLI wrapper yet
- No shared environment-variable configuration yet
- No packaging or installable command entry points yet
- Minimal tests only; most files are example workflows intended to be edited directly
