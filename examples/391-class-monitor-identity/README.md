# A static monitor and an instance monitor protect different reads

One JVM worker writes under its class monitor. The caller’s lock and the worker’s explicit or implicit synchronized method determine whether five is protected.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `MonitorIdentity#matched` (monitors) | The explicit shared class monitor protects the value until release, and join observes the worker write. | established |
| `MonitorIdentity#mixed` (monitors) | Holding the worker instance also protects the read against the class-locked writer. | refuted |
| `MonitorIdentity#synchronizedMethod` (monitors) | The static synchronized worker method uses the declaring class monitor. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 391`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm monitors --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/3 at opening and 0/3 at qualification, with 0 established and 0 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| monitors/matched | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/monitors/measurement.json) |
| monitors/mixed | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/monitors/measurement.json) |
| monitors/synchronizedMethod | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.01 s)](../../verification/java-semantics-gap/heap-and-gson/monitors/measurement.json) |

The separate schedule checker enumerated every completed sequentially consistent application-bytecode interleaving of the frozen two-thread callers, with successful start and join. Both class-matched callers returned true. The mixed caller returned both false and true, each reproduced on an original JVM.

[Instruction schedules and original JVM controls](../../verification/java-semantics-gap/monitor-schedules/measurement.json)

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
