# Deliveries

A thin Spring route in front of a [Crosscut](../crosscut/README.md) kernel, so that a check can be about what an
application's consumers observe at an entry point rather than about a method: the answer, the status, and the
boundary calls it attempts. It is the subject of the entry-point examples (the `effect-trace` tag in the
[router](../../README.md)), checked by `jvmcontract effects` ([`lib/README.md`](../../../lib/README.md#observation-specs)).

[`DeliveryFailures`](src/main/java/net/terminalvalue/deliveries/DeliveryFailures.java) is where a webhook dispatcher
reports a delivery that failed: `POST /deliveries/failures` with the receiver's HTTP status, whether the delivery may
be repeated safely, and how many attempts it has had. It asks Crosscut's
[`RetryPolicy`](../crosscut/src/main/java/net/terminalvalue/crosscut/retry/RetryPolicy.java) whether to try again,
and sends either a `RetryScheduled` to `delivery-retries` (answering 202) or a `DeadLettered` to
`delivery-dead-letters` (answering 200) through a `KafkaTemplate`. The decision is the kernel's; the route performs it,
as Crosscut's design rule asks of the framework glue around a kernel.

## Layout

```
src/main/java/     the route and the two payload records
src/stubs/java/    stand-ins for the Spring classes the route compiles against (KafkaTemplate, the web annotations):
                   on the class path, never in the build that is checked, so the template stays a framework type
src/test/java/     plain tests, run by Tests.main: the route against a template that records what it is sent
```

The app compiles with Crosscut's kernels: its build directory holds both, and a patch may change either. Nothing here
is part of Crosscut's own build, so Crosscut's recorded results don't depend on this app.

## Verify it

From the repository's root, with `jvmcontract` on the `PATH`:

```bash
cd examples/apps/deliveries
javac -parameters -g -d build/stubs $(find src/stubs/java -name '*.java')
javac -parameters -g -cp build/stubs -d build/main $(find src/main/java ../crosscut/src/main/java -name '*.java')
javac -parameters -g -cp build/main:build/stubs -d build/test $(find src/test/java -name '*.java')
java -ea -cp build/main:build/test:build/stubs net.terminalvalue.deliveries.Tests
jvmcontract observations build/main       # the route's observation spec
jvmcontract effects OLD/build/main build/main   # an earlier build's entry points, checked against this one's
```

[`build.py`](../../tools/build.py) does the same for an example (`TOOL_APPS["deliveries"]`): it compiles the unpatched
and the patched copies, runs the tests, and runs `jvmcontract effects` between them as the example's B9 check.
