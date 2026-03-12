# eCTF 2026 — System Overview

## Host Computer

The host computer is a general-purpose computer used to communicate with the HSM over a serial interface through a number of eCTF Tools. These tools will be used to initiate the various functionalities of the HSM device. All Host Tools communicating with the device will be written by the organizers.

## Hardware Security Module (HSM)

The main focus is on the HSM device — a generic security module that stores and transfers design files to other HSMs. The HSM communicates to the host computer over the Management Interface. HSMs communicate with each other over a separate Transfer Interface.

### Files

Secure file storage and transfer is the primary function. Files have:
- A file name (max 32 bytes, null-terminated)
- An associated Permission Group
- A Universally Unique Identifier (UUID, 16 bytes)
- Contents (max 8192 bytes)
- Files are stored in slots (max 8 slots)

### Management Interface

Physical interface utilized by a user to instruct the HSM to perform certain actions. Most actions are protected by a PIN. Communication follows the protocol defined in the Functional Requirements.

### Transfer Interface

Physically distinct from the management interface. When prompted by the management interface, two HSMs use the transfer interface to communicate files and file metadata between each other.

### Permission Groups

Permission groups are the critical security feature that HSMs rely on to authenticate one another. Every file belongs to one permission group. HSMs contain permission data for groups based on the permissions they have for that group.

#### Receive Permission
Enables HSMs to receive a file from a different HSM that contains files belonging to the group. If HSM A has receive permission for the engineering group and HSM B has engineering files, A can request those files from B. If A does not have the permission, B should refuse to transfer the file.

#### Write Permission
Enables an HSM to generate new files that belong to a specified permission group.

#### Read Permission
With the read permission, an HSM can return file contents back to the user over the Management Interface. The mere fact that an HSM stores a file does not mean it should be able to return the file contents. HSMs may contain files that they should not read.

## Development Resources

Teams are provided:
- **3x un-keyed MSP-LITO-L2228 boards** (Design Phase Boards) — for development. Cannot run Attack Phase designs provisioned by organizers. CAN be used to practice attacks against designs compiled locally from source.
- **3x keyed MSP-LITO-L2228 boards** (Attack Phase Boards) — for securely loading other teams' designs provided by organizers. Configured for Attack Phase, unusable during Design Phase.
- **4x XDS110-ETP-EVM USB Debuggers** — for programming, communicating with, and debugging boards
- **20x 6" Female/Female Jumper Wires** — for debugger connection and UART between two HSMs
