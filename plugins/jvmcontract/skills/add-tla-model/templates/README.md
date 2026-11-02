# The <system> protocol model

A TLA+ model of <the system> as <what interacts: services, handlers, queues, timers, callers>.
TLC, the TLA+ model checker, explores every interleaving of those parts within the bounds in [`<Name>.cfg`](<Name>.cfg) and checks the invariants below in every state it reaches.

| File | Content |
|---|---|
| [`<Name>.tla`](<Name>.tla) | The model. One action per <transaction / handler / relay / tick>; each action names the Java operation it stands for |
| [`<Name>.cfg`](<Name>.cfg) | The bounds TLC checks: <two customers, one seat, ...>, and the list of invariants |
| [`<Kernel>Contract.tla`](<Kernel>Contract.tla) | **Generated.** The decision rule, as the TLA+ operator `Decide(state, input)`, written by `jvmcontract tla` from the [behavioural contract](<Kernel>.<method>.contract) of `<pkg.Kernel#method>`, which `jvmcontract derive` produces by executing the compiled method on every input. Do not edit; `check.sh` regenerates it |
| [`check.sh`](check.sh) | Derives the contract from the current classes, fails if it changed, regenerates the operator, runs TLC |

## The invariants

- **<Name1>.** <The rule in the words of the people who own the system.>
- **<Name2>.** <...>
- **TypeOK.** Every variable stays in its type, within the bounds.

## What a pass means

*Within the bounds of `<Name>.cfg`, no interleaving of the modelled actions reaches a state that violates the invariants.*
It does not prove the Java code correct. The actions are a hand-written account of what each transaction reads and writes, and are only as faithful as that reading; what is not hand-written is the decision rule, `Decide`, which is generated from a contract that `jvmcontract` proves against the bytecode on every build, so a change to `<Kernel>` reaches the model through its proof.

Liveness ("every order eventually settles") is not checked; the invariants are safety properties.

## What the model leaves out

- <One per simplification: one order per customer; relays publish each entry once; a failed transaction is dead-lettered in one step; ...>
- <The owner's rules the kernel leaves implicit, written into the actions: ...>

## Run it

```bash
bash spec/check.sh             # the contract, the operator and TLC, in seconds
bash spec/check.sh --update    # after an intended change to the kernel: accept the new contract, then check
```

A violated invariant prints the shortest run that reaches it, one line per step with the action and the variables it changed.
To see the invariants bite, <the deliberate breakage that was tried: drop the guard in `X`, apply the kernel of ...>; `check.sh` then reports `<Invariant>` violated after <n> steps.
