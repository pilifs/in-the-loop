# The class-initialization model

A TLA+ model of class initialization (JVMS §5.5, JLS §12.4.2) as a concurrent system: the threads that need a class, the class's initialization state, the thread recorded as its initializer, and the threads blocked on the initialization lock.
TLC explores every interleaving for the threads in `ClassInit.cfg`, checks the invariants in every state it reaches, and checks that no reachable state is a deadlock: a state in which no thread can move.
This is approach D1 in [`approaches.md`](../../../approaches.md), applied to the fourth subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

| File | Content |
|---|---|
| [`ClassInit.tla`](ClassInit.tla) | The model. One action per operation of a thread: request the class (and act on the decision: run the initializer, wait, proceed, or get the error), request it again from inside the initializer, return from the initializer, throw from it. Each action names the runtime operation it stands for |
| [`ClassInit.cfg`](ClassInit.cfg) | The bounds TLC checks: three threads and one class, and the list of invariants |
| [`ClassInitContract.tla`](ClassInitContract.tla) | **Generated.** The runtime's decision rule, as the TLA+ operator `Decide(state, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/ClassInitialization.decide.contract) of `ClassInitialization#decide` |

The invariants:

- **UsedOnlyWhenInitialized.** A thread uses the class only once it is initialized: no thread reads a static field before `<clinit>` has assigned it, or calls a static method on a half-built class.
- **InitializedAtMostOnce.** The initializer runs at most once, whatever the threads do.
- **OneInitializer.** Only the recorded initializer runs the initializer.
- **TypeOK.**
- **No deadlock**, checked with `--deadlock`: the one thing the specification's step 3 (a recursive request by the initializing thread completes normally) exists for.

What the model leaves out: one class, with no superclass or superinterface to initialize first, so the deadlock between two classes whose initializers refer to each other from two threads is outside it; a thread that is done with the class stops; the decision and the state change are one atomic step, which is what the initialization lock provides.
The initializing thread may touch its own class while `<clinit>` runs (the `Recurse` action), and sees its static fields in whatever state they are in, which is what the specification allows and the model does not count as a use.

## Run it

```bash
cd examples/apps/mica
jvmcontract tla src/contract/ClassInitialization.decide.contract spec/ClassInitContract.tla
jvmcontract tlc spec/ClassInit.tla --deadlock --library ../../tools/tla/standard-modules
```

TLC checks 37 states in under a second. [Example 042](../../../042-class-init-that-proceeds-while-another-thread-initializes/README.md) shows a thread using the class two steps in, before its initializer has returned; [example 043](../../../043-class-init-that-waits-on-its-own-thread-deadlocks/README.md) shows the deadlock a runtime without step 3 reaches in four actions.
