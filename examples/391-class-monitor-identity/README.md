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

## Platform-thread construction

The ordinary checker stops when the original worker calls `Thread.<init>()`. On Temurin 21.0.13 that constructor reads the current platform thread. If the parent has an inheritable binding, the JDK copies it and calls the key's `childValue` on the parent thread before the worker starts. A stored null triggered one callback. An absent or removed key triggered none.

Eight fresh JVM runs kept the original worker class files. A callback that returned normally let the class-matched caller finish with the shared field at 6. A callback that threw escaped each of the three original callers as the identical exception, before the first write to the shared field. These runs install the parent binding explicitly. The schedule enumeration below starts with successful platform-thread construction. Reproduce the JVM controls with `python3 -B lib/benchmark/java-semantics-gap/monitor_startup.py --check`. [JDK call sites and observed values](../../verification/java-semantics-gap/monitor-startup/measurement.json)

## Measured results

The campaign's ordinary native checker decided 0/3 at opening and 0/3 at qualification, with 0 established and 0 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| monitors/matched | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.01 s)](../../verification/java-semantics-gap/decimal-transfer/callers/monitors/measurement.json) |
| monitors/mixed | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/monitors/measurement.json) |
| monitors/synchronizedMethod | [open (0.02 s)](../../verification/java-semantics-gap/opening/monitors/measurement.json) | [open (0.01 s)](../../verification/java-semantics-gap/decimal-transfer/callers/monitors/measurement.json) |

The separate schedule checker enumerated every completed sequentially consistent application-bytecode interleaving of the frozen two-thread callers, with successful start and join. Both class-matched callers returned true. The mixed caller returned both false and true, each reproduced on an original JVM.

[Instruction schedules and original JVM controls](../../verification/java-semantics-gap/monitor-schedules/measurement.json)

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
