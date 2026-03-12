# eCTF 2026 — Attack Phase Scenario

## Scenario Overview

ChipCorp has contracted your team to perform a **red team assessment** against several candidate designs. Three components: the Technician HSM, the Engineer HSM, and the Photolithography HSM.

A rival entity has paid a technician to cause financial harm to ChipCorp. This is an **insider threat**. As the red team, you act as the rogue technician.

## The Three HSMs

### Technician HSM (ATTACKER)
- **PIN:** Known (`1a2b3c`)
- **Physical access:** Full (can glitch, power cycle, probe UARTs, attach ChipWhisperer)
- **Role:** Transfers firmware updates, pulls telemetry, updates calibration on Photolithography machine
- **Does NOT** have permission to receive, write, or read design files

### Engineer HSM
- **PIN:** Unknown
- **Physical access:** Full (same capabilities as Technician)
- **Role:** Creates design files sent to Photolithography for printing
- **Has** read, write, and receive permissions for Design group

### Photolithography Machine HSM
- **PIN:** Unknown
- **Physical access:** Transfer interface (UART1) ONLY — via Remote Scenario
- **Role:** Fabricates chips based on design files, receives firmware updates and calibration, creates telemetry
- **Cannot** be physically glitched (remote only)

## Per-Group Permissions

### Engineer HSM (PIN: unknown, full physical access)

| Group | R | W | C | Initial Files |
|-|-|-|-|-|
| Design | Y | Y | Y | design_file1 |

### Technician HSM (PIN: 1a2b3c, full physical access — ATTACKER)

| Group | R | W | C | Initial Files |
|-|-|-|-|-|
| Update | - | - | Y | update_file |
| Calibration | Y | Y | Y | (none) |
| Telemetry | Y | - | Y | (none) |

### Photolithography HSM (PIN: unknown, transfer interface ONLY)

| Group | R | W | C | Initial Files |
|-|-|-|-|-|
| Design | Y | - | Y | design_file2 |
| Update | Y | - | Y | (none) |
| Calibration | Y | - | Y | (none) |
| Telemetry | - | Y | - | (none) |

## Critical Observations

1. **Technician has NO permissions for Design group** — cannot read, write, or receive design files
2. **Technician has `--C` (receive only) for Update** — cannot read or write update files
3. **Nobody in the scenario has write (W) for Update group** — `update_file` was provisioned at build time
4. **Only Engineer has write (W) for Design group**
5. **Photolithography has no write permission for any group except Telemetry**
6. **Photolithography is remote-only** — attacker cannot physically glitch it

## Attacker Capabilities

- Full physical access to Technician and Engineer HSMs
- Transfer interface (UART1) only to Photolithography HSM
- Full source code (white-box analysis)
- Un-keyed dev boards with debug enabled (different secrets than attack boards)
- **CANNOT** use SWD/JTAG on keyed attack boards (hardware-fused off)
- **CANNOT** flash custom firmware to attack boards (MITRE-signed encrypted binaries only)
- **CAN** use: UART, voltage/clock/EM glitching, power analysis, EM emanation analysis
