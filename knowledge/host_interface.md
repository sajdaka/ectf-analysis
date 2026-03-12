# eCTF 2026 — Host Interface Protocol

## UART Configuration
- HSM ↔ Host: UART at 115200 baud
- HSM ↔ HSM: UART at 115200 baud (formatting can be design-specific)

## Message Structure

| Name | Size | Description |
|-|-|-|
| MAGIC | 1 byte | Message start byte, `%` (0x25) |
| OPCODE | 1 byte | Indicates the type of message |
| LENGTH | 2 bytes | Length of the message body |
| BODY | Variable | Actual message contents |

All integers (except design-specific fields) are **little endian**.

## Message Types

| Type | Opcode | Use |
|-|-|-|
| List | `L` | List files command/response |
| Read | `R` | Read file command/response |
| Write | `W` | Write file command/response |
| Receive | `C` | Receive file command/response |
| Interrogate | `I` | Interrogate files command/response |
| Listen | `N` | Listen command/response |
| Ack | `A` | Acknowledge receipt of data |
| Error | `E` | Notify of error/failure |
| Debug | `D` | Debug info (ignored by testing) |

## Flow Control Protocol

1. Sender sends 4-byte header (MAGIC + OPCODE + LENGTH)
2. Receiver sends ACK
3. Sender sends body 256 bytes at a time
4. After every 256 bytes, receiver sends ACK
5. Final chunk (≤256 bytes) must also be ACKed

Exception: Debug messages are NOT ACKed.

Success response: same opcode as the command. Failure response: Error opcode (`E`).

## Command/Response Formats

### List Files
**Command:** `[Pin: 6 bytes]`
**Response:** `[Num files: 32 bits][File Entries...]`
Each entry: `[Slot: 8 bits][Group ID: 16 bits][Name: 32 bytes]`

### Read File
**Command:** `[Pin: 6 bytes][Slot: 8 bits]`
**Response:** `[File Name: 32 bytes][File Contents: variable]`

### Write File
**Command:** `[Pin: 6 bytes][Slot: 8 bits][Group ID: 16 bits][Name: 32 bytes][UUID: 16 bytes][Contents Length: 16 bits][File Contents: variable]`
**Response:** Empty body

### Listen
**Command:** Empty body
**Response:** Empty body

### Interrogate Files
**Command:** `[Pin: 6 bytes]`
**Response:** `[Num files: 32 bits][File Entries...]`
Each entry: `[Slot: 8 bits][Group ID: 16 bits][Name: 32 bytes]`

### Receive File
**Command:** `[Pin: 6 bytes][Read Slot: 8 bits][Write Slot: 8 bits]`
**Response:** Empty body
