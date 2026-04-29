---
name: proxmox-cli
description: >-
  CLI for managing Proxmox VE instances. JSON output for agents, rich tables for humans.
  TRIGGER: "proxmox", "proxmox-cli", "PVE", "virtual machine", "VM", "container", "LXC",
  "snapshot", "backup", "cluster", "node", "QEMU", "vzdump"
allowed-tools:
  - Bash
---

# proxmox-cli

CLI for managing Proxmox VE instances — VMs, containers, snapshots, backups, networking, storage, and cluster operations.

## ⚠️ #1 Rule: Global Flags BEFORE the Command

```bash
# ✅ CORRECT
proxmox-cli --json vm list
proxmox-cli --json --node pve1 vm show 100

# ❌ WRONG — silently ignored
proxmox-cli vm list --json
```

Global flags: `--json`, `--node/-n`, `--profile/-p`, `--url`, `--token-id`, `--token-secret`, `--insecure`

## Quick Start

```bash
# Auth via environment
export PROXMOX_API_URL="https://192.168.1.238:8006"
export PROXMOX_TOKEN_ID="root@pam!cli"
export PROXMOX_TOKEN_SECRET="your-secret"

# Common operations
proxmox-cli --json vm list
proxmox-cli --json vm show 100
proxmox-cli vm create --name web-01 --cores 2 --memory 4096 --disk 32
proxmox-cli vm destroy 100 --yes          # --yes required for destructive ops
proxmox-cli --json --node pve1 disk list  # --node for multi-node clusters
proxmox-cli --json nextid                 # next available VMID
```

## Safety

- Default profile is `agent` — blocks destructive ops without `--yes`
- Always pass `--yes` for destroy/delete commands
- Always pass all required flags to avoid interactive prompts

## Commands

17 groups + 1 standalone: `nextid`, `node`, `vm`, `ct`, `snapshot`, `backup`, `net`, `firewall`, `storage`, `template`, `iso`, `disk`, `pool`, `access`, `metrics`, `observe`, `apt`, `configure`

→ Full syntax: [commands/SKILL.md](commands/SKILL.md)
→ Agent recipes: [patterns/SKILL.md](patterns/SKILL.md)
