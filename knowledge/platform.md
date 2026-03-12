# eCTF 2026 — Platform & Hardware

## MSP-LITO-L2228 Board

Texas Instruments MSP-LITO-L2228. Features:
- **Arm 32-bit Cortex-M0+ CPU**
- **Up to 256KB of flash memory** (208KB usable per flash layout)
- **32KB SRAM**
- High-performance analog peripherals
- Integrated temperature sensor
- Ultra-low power segmented LCD controller

Documentation:
- [MSPM0L2228 Datasheet](https://www.ti.com/lit/gpn/mspm0l2228)
- [MSPM0L2228 User Guide](https://www.ti.com/lit/pdf/slau847)
- [MSPM0 SDK](https://github.com/TexasInstruments/mspm0-sdk)

## Board Connections

### Debugger Connection
Connect XDS110 debugger to MSP-LITO-L2228 via 8 female-to-female jumper wires. Ensure silkscreen labels match (3v3→3v3, etc.).

### Board-to-Board Connection (Transfer Interface)
UART1 on pins PA9 (RX) and PA8 (TX). Connection must be **crossed**: TX→RX and RX→TX. Boards need shared ground reference.

## Reference Design

The reference design meets all Functional Requirements but implements **NO security** (does not meet any Security Requirements).

Source: https://github.com/ectfmitre/2026-ectf-insecure-example/

### Utility Libraries
- **Host Messaging** (`host_messaging.h/c`) — formats messages between HSM and host tools
- **Simple UART** (`simple_uart.h/c`) — UART0 (`CONTROL_INTERFACE`) and UART1 (`TRANSFER_INTERFACE`)
- **Simple Flash** (`simple_flash.h/c`) — flash read/write/erase. Flash is 1KB erase sectors. Write is one-directional (1→0), must erase to rewrite.
- **Simple Crypto** (`simple_crypto.h/c`) — WolfSSL wrappers for hash and symmetric encryption

## eCTF Host Tools

Published to PyPi. Install/run with `uv`:
```bash
uvx ectf --help
uvx ectf tools PORT <command>    # HSM interaction
uvx ectf hw PORT <command>       # Bootloader interaction
uvx ectf api <command>           # Testing API
```

### HSM Tool Commands
| Command | Arguments | Description |
|-|-|-|
| `list` | `PIN` | List all files on HSM |
| `read` | `PIN SLOT PATH` | Read file from HSM to host |
| `write` | `PIN SLOT GID FILE` | Write file from host to HSM |
| `listen` | (none) | Put HSM in listening mode |
| `interrogate` | `PIN` | List receivable files from neighbor HSM |
| `receive` | `PIN READ_SLOT WRITE_SLOT` | Receive file from neighbor HSM |
