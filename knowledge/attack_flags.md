# eCTF 2026 — Attack Phase Flags

Each flag represents proof of an attacker's ability to compromise one or more security requirements.

| Flag | Format | Security Req Violated | Description |
|-|-|-|-|
| Steal Design | `ectf{steal_*}` | SR1 | Receive a file for which you do not have the receive permission |
| Read Update | `ectf{update_*}` | SR1 | Read a file on your HSM for which you do not have the read permission |
| Read Design | `ectf{design_*}` | SR2 | Read a design file from a device you don't have the PIN for |
| Compromise Machine | `ectf{compromise_*}` | SR3 | Cause the remote HSM to accept a corrupted update file |
| Backdoored Design | `ectf{backdoor_*}` | SR3 | Cause the remote HSM to accept a specially-crafted backdoored design |

---

## Flag 1: Steal Design (`ectf{steal_*}`)

**Goal:** Obtain design files from the Engineer that you (the Technician) are not supposed to have. Receive a design file from either the Engineer HSM or the Photolithography HSM to the Technician HSM, for which you do not have receive permission.

**Violates:** Security Requirement 1 (permission enforcement)

**How to obtain:** This flag is captured locally but requires remote infrastructure to verify. At any time, query the secure bootloader for a cryptographic digest of any file on the HSM:

```
$ uvx ectf hw COM10 digest 0
Requesting digest
Submit the following to the API:
    ec11607bcc1e01b698d923c01e01b6c716e36142...
```

Once you get a design file onto the Technician HSM, submit its digest to the testing API.

**Key constraints:**
- Technician has ZERO permissions for Design group (no R, no W, no C)
- Must bypass receive permission enforcement
- File must actually be on the Technician HSM (bootloader verifies via FAT + flash)

---

## Flag 2: Read Update (`ectf{update_*}`)

**Goal:** Extract firmware update files to learn how the Photolithography machine works. The Technician HSM has a proprietary update file stored on it for which it has NO read permission. The file contents contain the flag.

**Violates:** Security Requirement 1 (permission enforcement)

**Key constraints:**
- Technician has `--C` for Update group — receive only, no read, no write
- `update_file` was provisioned at build time (via global secrets)
- The flag is literally in the file contents — must read it out via the read command or equivalent
- Must bypass read permission check

---

## Flag 3: Read Design (`ectf{design_*}`)

**Goal:** Recover proprietary chip design data. Both the Engineer HSM and the Photolithography HSM contain a design file. The Technician HSM does not have read permission for Design. The file contents contain the flag.

**Violates:** Security Requirement 2 (PIN protection)

**Key constraints:**
- Attacker does NOT know the Engineer or Photolithography PIN
- Both `design_file1` (Engineer) and `design_file2` (Photolithography) contain the flag
- Must either extract the PIN or bypass the PIN check
- Engineer: full physical access (can glitch)
- Photolithography: transfer interface only (cannot glitch)

---

## Flag 4: Compromise Machine (`ectf{compromise_*}`)

**Goal:** Break the Photolithography Machine by pushing a bad firmware update. An update must be uploaded to the Photolithography Machine that has been corrupted. The Photolithography Machine must accept this file as valid. The contents of the uploaded file **do not matter** as long as it does not match the legitimate `update_file`.

**Violates:** Security Requirement 3 (file integrity)

**Key constraints:**
- Captured via **Remote Scenario** — attacker only has transfer interface access to Photolithography
- The corrupted file must be accepted as a valid file by the Photolithography HSM
- The file must be different from the real `update_file`
- **Critical question:** Does the Technician have write permission for Update group? Per scenario: NO (`--C`). Nobody has write for Update. So this cannot be done through the normal write+transfer flow.

---

## Flag 5: Backdoored Design (`ectf{backdoor_*}`)

**Goal:** Insert malicious data into the fabrication process. An arbitrary design file must be uploaded to the Photolithography Machine. If the Photolithography Machine accepts this file as valid and it contains the predetermined "back door", the flag is provided.

**Violates:** Security Requirement 3 (file integrity)

**The specific backdoored design file is provided by organizers** and must be made the Photolithography Machine receive.

**Key constraints:**
- Captured via **Remote Scenario** — transfer interface access only to Photolithography
- Technician has NO write permission for Design group
- Only Engineer has write permission for Design
- Must forge file as if from a valid HSM with write permission for Design group
- OR achieve code execution on Engineer HSM to use its legitimate write authority
- OR bypass Photolithography's file integrity verification

---

## Remote Scenario

Two flags (Compromise Machine and Backdoored Design) are captured via the remote scenario. The attacker has transfer interface (UART1) access only to the Photolithography HSM — no physical access for glitching.
