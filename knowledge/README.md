# eCTF 2026 Specification — Split Reference

The full eCTF spec has been split into focused sections for efficient searching. The original monolithic file is at `~/.claude/memory/ectf_spec.md` (4529 lines).

## Section Index

| File | Contents | Lines | Priority |
|-|-|-|-|
| [attack_flags.md](attack_flags.md) | All 5 attack flags: goals, constraints, how to capture | ~130 | CRITICAL |
| [attack_scenario.md](attack_scenario.md) | 3-HSM scenario, per-group permissions, attacker capabilities | ~100 | CRITICAL |
| [security_reqs.md](security_reqs.md) | Security Requirements 1, 2, 3 | ~30 | CRITICAL |
| [detailed_specs.md](detailed_specs.md) | PINs, permissions strings, FAT, flash layout, timing, sizes | ~100 | HIGH |
| [host_interface.md](host_interface.md) | UART protocol, message format, all command/response tables | ~100 | HIGH |
| [functional_reqs.md](functional_reqs.md) | Build system + all 6 HSM commands | ~80 | HIGH |
| [bootloader.md](bootloader.md) | Secure/insecure bootloader, file digests, bootloader tools | ~50 | MEDIUM |
| [system_overview.md](system_overview.md) | HSM architecture, interfaces, permissions, groups, dev resources | ~70 | MEDIUM |
| [platform.md](platform.md) | Board specs, connections, reference design, host tools CLI | ~80 | LOW |

## Quick Access by Task

**Analyzing a target team's firmware:**
→ Read `security_reqs.md` + `attack_flags.md` + `attack_scenario.md`

**Understanding protocol/message formats:**
→ Read `host_interface.md` + `detailed_specs.md`

**Understanding file storage/FAT:**
→ Read `detailed_specs.md` (Flash Layout + FAT sections)

**Understanding build/provisioning:**
→ Read `functional_reqs.md` (Build sections)

**Understanding hardware constraints:**
→ Read `platform.md` + `bootloader.md`
