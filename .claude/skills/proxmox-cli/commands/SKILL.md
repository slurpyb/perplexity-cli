---
name: proxmox-cli-commands
description: Full command syntax for all proxmox-cli subcommands
---

# proxmox-cli — Full Command Reference

> **Remember:** `--json`, `--node`, `--profile` are GLOBAL — place them BEFORE the command group.

## nextid

```bash
proxmox-cli --json nextid
```

Returns: `{"vmid": 101}` — the next available VM/CT ID.

---

## node

```bash
proxmox-cli --json node list                     # List all nodes
proxmox-cli --json node status <NODE>            # Node details (CPU, memory, uptime)
proxmox-cli --json node tasks [--limit N]        # Recent tasks
```

---

## vm (QEMU Virtual Machines)

```bash
proxmox-cli --json vm list                       # List all VMs
proxmox-cli --json vm show <VMID>                # VM details
proxmox-cli vm create --name <NAME> [OPTIONS]    # Create VM
proxmox-cli vm destroy <VMID> --yes              # Delete VM (requires --yes)
proxmox-cli vm start <VMID>                      # Start VM
proxmox-cli vm stop <VMID>                       # Stop VM
proxmox-cli vm restart <VMID>                    # Restart VM
```

Create options: `--name`, `--cores`, `--memory` (MB), `--disk` (GB), `--storage`, `--iso`, `--net`, `--ostype`, `--start`

---

## ct (LXC Containers)

```bash
proxmox-cli --json ct list                       # List all containers
proxmox-cli --json ct show <VMID>                # Container details
proxmox-cli ct create --name <NAME> [OPTIONS]    # Create container
proxmox-cli ct destroy <VMID> --yes              # Delete container
proxmox-cli ct start <VMID>                      # Start container
proxmox-cli ct stop <VMID>                       # Stop container
proxmox-cli ct restart <VMID>                    # Restart container
```

Create options: `--name`, `--cores`, `--memory` (MB), `--disk` (GB), `--storage`, `--template`, `--password`, `--net`, `--start`, `--unprivileged`

---

## snapshot

```bash
proxmox-cli --json snapshot list <VMID>          # List snapshots
proxmox-cli snapshot create <VMID> --name <NAME> [--description <DESC>]
proxmox-cli snapshot rollback <VMID> --name <NAME>
proxmox-cli snapshot delete <VMID> --name <NAME> --yes
```

---

## backup

```bash
proxmox-cli --json backup list [--vmid <VMID>] [--storage <STORE>]
proxmox-cli backup create <VMID> [--storage <STORE>] [--mode snapshot|stop|suspend] [--compress zstd|gzip|lzo|none]
proxmox-cli backup restore <VMID> --archive <FILE> [--storage <STORE>] [--force]
proxmox-cli backup delete <VOLUME> --yes
proxmox-cli --json backup notes <VOLUME>
```

---

## net

```bash
proxmox-cli --json net list                      # All network interfaces
proxmox-cli --json net bridges                   # Linux bridges only
proxmox-cli net create-bridge --name <NAME> [--ports <PORTS>] [--ip <CIDR>] [--gateway <GW>] [--autostart] [--comments <TEXT>]
proxmox-cli net delete-bridge <NAME> --yes
```

---

## firewall

```bash
proxmox-cli --json firewall list                 # List cluster firewall rules
proxmox-cli firewall add --action <accept|drop|reject> --type <in|out|group> [--source <CIDR>] [--dest <CIDR>] [--dport <PORT>] [--proto <tcp|udp|icmp>] [--enable] [--comment <TEXT>]
proxmox-cli firewall delete <POS> --yes
```

---

## storage

```bash
proxmox-cli --json storage list                  # List storage pools
```

---

## template

```bash
proxmox-cli --json template list [--storage <STORE>]     # Downloaded templates
proxmox-cli --json template available [--storage <STORE>] # Available for download
proxmox-cli template download --template <NAME> [--storage <STORE>]
```

---

## iso

```bash
proxmox-cli --json iso list [--storage <STORE>]  # List ISOs
proxmox-cli iso download --url <URL> [--filename <NAME>] [--storage <STORE>]
proxmox-cli iso delete <VOLUME> --yes
```

---

## disk

```bash
proxmox-cli --json disk list                     # Physical disks
proxmox-cli --json disk smart <DEVICE>           # SMART health data
```

---

## pool

```bash
proxmox-cli --json pool list                     # List resource pools
proxmox-cli --json pool show <POOL>              # Pool details + members
proxmox-cli pool create --name <NAME> [--comment <TEXT>]
proxmox-cli pool delete <POOL> --yes
proxmox-cli pool add-member <POOL> --vmid <VMID> [--storage <STORE>]
```

---

## access

```bash
proxmox-cli --json access users                  # List users
proxmox-cli access create-user --userid <USER@REALM> [--password <PASS>] [--email <EMAIL>] [--firstname <NAME>] [--lastname <NAME>] [--groups <GROUPS>] [--enable]
proxmox-cli --json access roles                  # List roles
proxmox-cli access create-role --roleid <ROLE> --privs <PRIV1,PRIV2,...>
proxmox-cli --json access tokens --userid <USER@REALM>   # List API tokens
proxmox-cli access create-token --userid <USER@REALM> --tokenid <ID> [--privsep] [--expire <EPOCH>] [--comment <TEXT>]
proxmox-cli --json access acl                    # List ACLs
proxmox-cli access grant --path <PATH> --role <ROLE> [--users <USER>] [--groups <GROUP>] [--tokens <TOKEN>] [--propagate]
```

---

## metrics

```bash
proxmox-cli --json metrics node [--timeframe hour|day|week|month|year]
proxmox-cli --json metrics vm <VMID> [--timeframe hour|day|week|month|year]
```

---

## observe

```bash
proxmox-cli --json observe resources [--type vm|lxc|node|storage]  # Cluster resources
proxmox-cli --json observe top [--sort cpu|memory|disk]            # Top consumers
proxmox-cli --json observe tasks [--limit N]                       # Recent cluster tasks
```

---

## apt

```bash
proxmox-cli --json apt list                      # Available updates
proxmox-cli apt refresh                          # Refresh package index
proxmox-cli --json apt changelog <PACKAGE>       # Package changelog
```

---

## configure

```bash
proxmox-cli --json configure list                # List profiles
proxmox-cli configure add <NAME> --url <URL> --token-id <ID> --token-secret <SECRET> [--default] [--insecure]
proxmox-cli configure set-default <NAME>
```

**Note:** `configure add` will prompt interactively if flags are omitted — always pass all required flags.
