# eCTF 2026 — Detailed Specifications

## Design Package
Generate Secrets script must be a pip-installable Python package named `ectf26_design`.

```python
from ectf26_design.gen_secrets import gen_secrets

def gen_secrets(groups: list[int]) -> bytes:
    pass
```

Takes a list of valid group IDs, returns bytes (secrets) passed to future build steps.

## File Allocation Table (FAT)

Used by the bootloader to calculate cryptographic file digests. Must contain at least 8 entries of the following 24-byte struct. **FAT must be based at flash address 0x3A000.**

| Offset | Size | Name | Description |
|-|-|-|-|
| 0x0 | 16 | UUID | UUID of the file in that slot |
| 0x10 | 2 | Length | Length of the file |
| 0x12 | 2 | Padding | Unused (32-bit alignment) |
| 0x14 | 4 | Addr | Starting flash address of the file |

## Flash Layout

| Offset | Size | Name | Description |
|-|-|-|-|
| 0x0 | 0x6000 | Bootloader | Reserved for eCTF bootloader |
| 0x6000 | 0x34000 | APP1 | Design's flash region. IVT must be at base. |
| 0x3A000 | 0x400 | FAT | File Allocation Table (MUST be here) |
| 0x3A400 | 0x5C00 | APP2 | Additional flash region for design |

## Permission Strings

Format: `1234=RW-:aabb=RWC:1a2b=--C`
- Colon-separated list of permissions
- Each entry: `<group_id>=<permission>`
- Group ID: 16-bit hex, 4 chars, no `0x` prefix (e.g., `4b1d`)
- Permission: 3-char string, present = opcode letter, absent = `-` (e.g., `RWC`, `R--`, `--C`)

## PINs

A PIN shall be exactly **6 lowercase hexadecimal characters** (0-9, a-f).

## Timing Requirements

| Operation | Maximum Time |
|-|-|
| Device Wake | 1 second |
| List Files | 500 milliseconds |
| Read File | 3000 milliseconds |
| Write File | 3000 milliseconds |
| Receive File | 3000 milliseconds |
| Interrogate | 1000 milliseconds |
| Any Operation Where Invalid PIN Provided | **5 seconds** |

## Size Constraints

| Component | Size |
|-|-|
| Group ID | 16 bits |
| File UUID | 16 bytes |
| File Name | Max 32 bytes (null-terminated) |
| File Content Size | Max 8192 bytes |
| File Slots | 8 slots |
| Min groups (deployment) | 32 groups |
| Min groups (per HSM) | 8 groups |

## Allowed Programming Languages

Pre-approved: **C, C++, and Rust**. Others require organizer approval.

If using a language with a panic handler, design must still adhere to timing requirements and should not enter an infinite loop in response to any normal input.
