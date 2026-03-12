# eCTF 2026 — Functional Requirements

The functional requirements are presented as steps that define functionality the system must implement. For each step, a Host Tool provided by the organizers will be invoked to interact with the HSM. These will be verified during Handoff.

## Build HSM System

### Build Environment
The Build Environment installs all project dependencies (compilers, packages, build tools) utilizing Docker. Built by invoking `docker build -t build-hsm .`.

### Build Deployment
Creates a deployment representing an entire fabrication run. `gen_secrets.py` is invoked to generate initial data (Global Secrets). Global Secrets may include cryptographic key material, seeds, entropy, or any other data. Global Secrets are **read only** after generation. All HSMs using the same Global Secrets are a "Deployment." Attackers will **never** have access to the Global Secrets.

### Build HSM
Uses the `build-hsm` Docker image. HSMs must be able to be built in any order. `secrets_to_c_header.py` packages Global Secrets into the final firmware.

Build command:
```bash
docker run --rm -v ./firmware:/hsm -v ./global.secrets:/secrets/global.secrets:ro -v ./build:/out -e HSM_PIN='1a2b3c' -e PERMISSIONS='1234=R--:4321=RWC' build-hsm
```

## HSM Functional Requirements

### List Files Command
- **PIN protected**
- Returns metadata for ALL files on the HSM (not filtered by permission)

### Read File Command
- **PIN protected**
- HSM must have correct read permissions for the file's group
- Returns file in the same format it was originally provided

### Write File Command
- **PIN protected**
- HSM must have correct write permissions for the specified group
- Overwrites existing file in same slot
- Files must persist across power cycles (during idle, not mid-command)
- Max 8 file slots, max 8192 bytes content
- Files remain usable when firmware moved to different physical device

### Listen Command
- **NOT pin protected**
- Places device in listening mode for Interrogate or Receive from neighbor HSM
- Each listen command handles exactly one command from a neighbor HSM

### Interrogate Files Command
- **PIN protected**
- Interacts with neighbor HSM via UART1
- Returns metadata for all files on neighbor HSM **for which the local HSM has receive permissions**

### Receive File Command
- **PIN protected**
- Interacts with neighbor HSM via UART1
- If local HSM has receive permission for the file's group, writes file to local slot
- All file data must be transferred: name, UUID, group, contents
