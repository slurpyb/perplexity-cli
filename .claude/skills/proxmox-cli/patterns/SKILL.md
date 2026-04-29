---
name: proxmox-cli-patterns
description: Agent recipes and scripting patterns for proxmox-cli
---

# proxmox-cli — Agent Patterns & Recipes

## JSON Extraction with jq

```bash
# VM names
proxmox-cli --json vm list | jq -r '.[].name'

# Running VMs only
proxmox-cli --json vm list | jq '[.[] | select(.status == "running")]'

# VM count by status
proxmox-cli --json vm list | jq 'group_by(.status) | map({status: .[0].status, count: length})'

# Node memory usage percentage
proxmox-cli --json node status pve1 | jq '(.memory.used / .memory.total * 100 | floor | tostring) + "%"'

# Storage usage
proxmox-cli --json storage list | jq '.[] | {storage: .storage, used_pct: ((.used / .total * 100) | floor)}'
```

## Error Handling

```bash
# Check if VM exists before acting on it
if output=$(proxmox-cli --json vm show 100 2>/dev/null); then
  status=$(echo "$output" | jq -r '.status')
  echo "VM 100 is $status"
else
  echo "VM 100 not found"
fi

# Exit code: 0 = success, 1 = error
proxmox-cli --json vm start 100
if [ $? -ne 0 ]; then
  echo "Failed to start VM 100" >&2
fi
```

## Provisioning Workflow

```bash
# 1. Get next available ID
VMID=$(proxmox-cli --json nextid | jq -r '.vmid')

# 2. Create VM
proxmox-cli vm create \
  --name "app-$VMID" \
  --cores 4 \
  --memory 8192 \
  --disk 50 \
  --storage local-lvm \
  --net "virtio,bridge=vmbr0" \
  --start

# 3. Verify creation
proxmox-cli --json vm show "$VMID" | jq '{vmid, name, status}'
```

## Snapshot Workflow

```bash
VMID=100

# Create pre-update snapshot
proxmox-cli snapshot create "$VMID" \
  --name "pre-update-$(date +%Y%m%d)" \
  --description "Before package updates"

# ... do work ...

# Rollback if something went wrong
proxmox-cli snapshot rollback "$VMID" --name "pre-update-$(date +%Y%m%d)"

# Or clean up snapshot
proxmox-cli snapshot delete "$VMID" --name "pre-update-$(date +%Y%m%d)" --yes
```

## Backup Workflow

```bash
# Create backup of VM 100
proxmox-cli backup create 100 --mode snapshot --compress zstd

# List backups for a VM
proxmox-cli --json backup list --vmid 100 | jq '.[] | {volid, size, ctime}'

# Restore backup to a new VM
NEWID=$(proxmox-cli --json nextid | jq -r '.vmid')
proxmox-cli backup restore "$NEWID" --archive "local:backup/vzdump-qemu-100-2024_01_01-00_00_00.vma.zst"
```

## Monitoring Patterns

```bash
# Cluster resource overview
proxmox-cli --json observe resources | jq '.[] | {type, id, status, cpu, mem: .maxmem}'

# Top CPU consumers
proxmox-cli --json observe top --sort cpu | jq '.[0:5] | .[] | {name, cpu}'

# Recent failed tasks
proxmox-cli --json observe tasks --limit 50 | jq '[.[] | select(.status != "OK")] | .[0:10]'

# Node health check
for node in $(proxmox-cli --json node list | jq -r '.[].node'); do
  echo "=== $node ==="
  proxmox-cli --json node status "$node" | jq '{cpu: .cpu, memory_pct: (.memory.used / .memory.total * 100 | floor)}'
done
```

## Batch Operations

```bash
# Stop all VMs in a list
for vmid in 100 101 102; do
  proxmox-cli vm stop "$vmid"
done

# Snapshot all running VMs
proxmox-cli --json vm list | jq -r '.[] | select(.status == "running") | .vmid' | while read vmid; do
  proxmox-cli snapshot create "$vmid" --name "batch-$(date +%Y%m%d)"
done
```

## Multi-Node Operations

```bash
# List VMs across all nodes
for node in $(proxmox-cli --json node list | jq -r '.[].node'); do
  echo "--- $node ---"
  proxmox-cli --json --node "$node" vm list | jq '.[] | {vmid, name, status}'
done

# Check disk health on specific node
proxmox-cli --json --node pve2 disk list | jq '.[] | {devpath, type, size, health: .wearout}'
```

## Access Management

```bash
# Create a read-only user for monitoring
proxmox-cli access create-user --userid monitor@pve --password "secure-pass" --enable
proxmox-cli access create-role --roleid Monitor --privs "VM.Audit,Sys.Audit,Datastore.Audit"
proxmox-cli access grant --path / --role Monitor --users monitor@pve --propagate

# Create API token for automation
proxmox-cli access create-token --userid root@pam --tokenid automation --privsep
```
