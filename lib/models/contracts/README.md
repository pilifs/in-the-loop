# `lib/models/contracts/`: the contract library

Contracts for the gaps of jvmcontract's own checker: calls into the JDK that it does not implement, which it refuses
under `--gaps strict`. Each one here was checked once, and the record of that check is in `checked.json`, so a run
under `--gaps advised` applies it at its call without the agent writing it again and without checking it again
(step 3d of [`llm-dlc/loops/sound-verdicts.md`](../../../llm-dlc/loops/sound-verdicts.md); the code is
[`src/contract_library.rs`](../../src/contract_library.rs)). The files are built into the binary, as the models are.

- **A file per JDK class**, `java.util.Random.contracts`, in the format `--contracts` reads (`kind: gap-contracts`,
  then a block per gap under its id; see [`lib/README.md`](../../README.md) and
  [`src/gap_contracts.rs`](../../src/gap_contracts.rs)). The id names the JDK the contract was written for.
- **`checked.json`**: a record per check, giving the contract's digest (over its gap and its keys, so a comment or a
  blank line does not change it), the JDK it was checked on, the jvmcontract that checked it, and the evidence, with
  the proof against the JDK's bytecode and the JVM test as the run reports them. It is written by
  `jvmcontract gap-contracts --dir lib/models/contracts --record`, never by hand.

A run applies a contract on its record only while the record holds: the same contract, the same JDK, and for a proof
the same class file in the JDK image. Otherwise the run checks the contract itself, as it does an agent's, and says
so in a `note:`. After a JDK upgrade, then, every contract is checked again in each run until the library is
recorded on the new JDK. A contract written for another JDK is checked under the new JDK's id. A gap the agent's
`--contracts` has a contract for takes the agent's, even when it is refused: a wrong contract goes back to the agent
rather than being replaced by the library's. `--no-contract-library` turns the library off.

## Adding a contract

1. Write the block in the class's file, from the JDK's documentation of the call, not its source, with a
   `written-by:` line that says who wrote it and from what. A template comes from a run under `--gaps advised`
   that reaches the gap (`contracts.template` in its work directory).
2. Run `jvmcontract gap-contracts --dir lib/models/contracts`. It proves each contract against the JDK's bytecode
   where it can and tests it on a real JVM. It exits 1 when a contract is refused (the JVM refutes it, or the engine
   cannot apply it) or has no record that holds.
3. When nothing is refused, run it again with `--record`, rebuild, and add the file to `FILES` in
   `src/contract_library.rs` if it is new. A unit test checks that `FILES` lists every file here. The integration test
   `the_contract_library_closes_gaps_on_its_records_and_max_trust_refuses_trusted_contracts` checks that every record
   holds on the JDK the library was recorded on.

Keep only contracts the JVM can test or the checker can prove. A trusted one (a parameter of an object type, say)
would rest every verdict that used it on whoever wrote it, and `--max-trust 0` refuses it anyway.

## What is here (recorded on JDK 25.0.4.1 and 25.0.5)

| Class | Calls | Evidence |
|---|---|---|
| `java.lang.Integer` | `numberOfTrailingZeros(int)` | proved |
| `java.lang.StringBuilder` | `<init>(int)` | tested |
| `java.util.ArrayList` | `<init>(int)` | tested |
| `java.util.HashMap` | `<init>(int)` | tested |
| `java.util.HashSet` | `<init>(int)` | tested |
| `java.util.Random` | `<init>(long)`, `nextInt(int)`, `nextBytes(byte[])` | tested |

`Integer.numberOfLeadingZeros` and `Long.numberOfLeadingZeros` had proved contracts here until the tool's own checker
modelled them exactly (`Engine::call_jdk_static`): a call it reproduces is no gap, and a contract for one is refused,
so they were taken out with their records.
