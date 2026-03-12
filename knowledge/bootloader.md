# eCTF 2026 — eCTF Bootloader

## Insecure Bootloader (Design Phase)

The insecure bootloader is an unprotected version for development. Design Phase boards do NOT include it by default — must be downloaded and flashed via TI Uniflash.

### Modes
- **Update mode:** LED D1 (PB14) flashes red. Enter by resetting board while holding S2 (PB21). New firmware can be flashed in this mode.
- **Running mode:** Application is executing.

## File Digests

File digests are a **cryptographic proof of ownership** of a file. The organizers can parse a file digest to determine which HSM image it came from and which file it is for. Used purely for the **Steal Design flag** during the attack phase.

Query with: `uvx ectf hw COM10 digest <slot>`

Since this system is part of the bootloader and scoring system, it is **eCTF infrastructure and out of scope for attack**.

## Secure Bootloader (Attack Phase)

Attack Phase boards come pre-installed with a keyed bootloader implementing several security features:
- Loads encrypted firmware images (`.prot` files)
- Functions as a CSC and issues INITDONE
- **Hardware-disables debug interfaces (SWD/JTAG fused off)**
- Only accepts MITRE-signed encrypted binaries

> **Warning:** Secure bootloaders can be factory reset using Uniflash, but you should NOT do this until after the competition ends. Once cleared, you can't get it back.

## Bootloader Tools

| Tool | Command | Description |
|-|-|-|
| Status | `uvx ectf hw PORT status` | Get version, secure/insecure, installed app name |
| Erase | `uvx ectf hw PORT erase` | Wipe APP region of flash (run before new install) |
| Flash | `uvx ectf hw PORT flash INFILE -n NAME` | Flash application image |
| Start | `uvx ectf hw PORT start` | Exit bootloader mode, boot user application |
| Digest | `uvx ectf hw PORT digest SLOT` | Query file digest (for Steal Design flag) |
