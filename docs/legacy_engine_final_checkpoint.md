# Legacy Engine Final Checkpoint

Date: 2026-08-21

This repository closes the legacy Low-PCode backward-slice development line
with the generated frontier cases through `TV2C688` and `TV2R346`.

## Validation policy

- A positive case passes only when every required expected source is present.
- Additional sources are recorded as `PRECISION_PENDING` and do not fail the
  recall gate.
- An explicit `expected_no_sources` case remains strict: any reported source
  is a failure.
- Expected manifests and generated Low-PCode are test oracles, not engine
  semantics.

## Independent final result

The final cache-disabled NetworkX reference regression was saved under
`output/harness/audit_gpt56_green24h_final_networkx`.

| Suite | Pass | Fail | Error | Precision pending | Negative failures |
|---|---:|---:|---:|---:|---:|
| 09_tdo_testbed | 488 | 0 | 0 | 30 | 0 |
| 10_tdo_testbed_UE | 958 | 0 | 0 | 38 | 0 |
| Total | 1446 | 0 | 0 | 68 | 0 |

The engine unit suite passed 58/58, its Python modules compiled successfully,
and the harness design lint reported no violations.

## Role after closure

Suite09 and Suite10 remain the behavioral contract for the V2 engine. New V2
work must run beside the legacy engine until parity is demonstrated. The OLLVM
Suite12 corpus remains an adversarial future layer and is not allowed to drive
the initial V2 core semantics.
