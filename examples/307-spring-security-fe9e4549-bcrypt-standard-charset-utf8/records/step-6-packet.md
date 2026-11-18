# Example 307 ahead of the preservation stream's step 6: what was measured, and what it means

Written 2026-11-17 by a session the user brought in to get ahead of step 6 of
`llm-dlc/loops/domain-advances-preservation.md` while the stream was still on 287. It is guidance within step 6,
not an instruction: the brief, the frozen claim and the stream's own evidence come first. Nothing here changes the
claim, the checker, 307's notes or any stream's files. Every statement below names the file or the command it rests
on. The checker probed is the stream's `rmvpqswzxlyv` (git `e461ac1d2c5f`, its last commit before the I010 fix),
exported and built apart.

## In short

1. **The ties do not reach 307 at its frozen bound.** The claim fixes unwind 513, which is within every loop of
   bcrypt, so no loop is summarized and nothing is tied: the checker unwinds the cipher and is killed at 4 GB in
   under a minute. At the default unwinding the ties apply and the run ends at the time limit, as 287's does.
2. **The claim's own note names the way out**: "a checked summary of the unchanged callee `hashpw(byte[],String)`,
   bound to its actual bytecode". That callee's code is the same in both revisions and in the mutant, writes
   nothing its caller can see, and reads five final static arrays that nothing outside the initializer writes. With
   it taken as one function, what is left to prove is that the two conversions give the same bytes.
3. **The conversions are the first stops, and both need a model.** `preservation` stops in 1 s at the previous
   revision's `getBytes("UTF-8")`; `mutant-preservation` stops at the mutant's `StandardCharsets.US_ASCII`. An
   80-line prototype models both; twelve countermodel pairs tell it from two wrong models.
4. **The mutant's refutation needs a witness search that survives a candidate that does not replay.** With the
   callee abstracted, most candidates are not witnesses (four of the seven salts are invalid, a null password
   throws first, bytes past the 72nd are never read). `é` under either valid cost-5 or cost-6 salt is one.
5. **The example route drops the claim's assumption.** `build.py 307 --task preservation` passes no `--assume`
   for an equivalence task, so the route checks every salt of up to 80 units, not the claim's seven. The
   driver module the brief points to expects an adapter and pinned JARs, and 307 has neither.
6. **The same boundary exists for 287**: `crypt_raw`'s code is the same in 6.3.7 and 6.3.8, and the only change to
   `hashpw(byte[], String, boolean)` is a nine-instruction guard near its entry.

## 1. Where the checker stops today

Six capped probes (`records/step-6-probes.json`; 4 GB, 300 s, one at a time). The command is the claim's, as the
route would give it plus the claim's `--assume`:

| Probe | Pair | Unwind | Ends | After |
|---|---|---|---|---|
| the claim's pair | before, after | 513 (frozen) | no verdict: `String.getBytes` not modelled | 1.2 s |
| the mutation pair | after, mutant | 513 | no verdict: `StandardCharsets.US_ASCII` not read | 2.5 s |
| a pair made to reach the cipher (after, and after with its `return` split in two) | | 513 | killed: out of memory at 4 GB | 62 s |
| the same pair | | default, 16 (a trial) | no verdict: time limit; 36,061 values tied, 203 of 240 s solving | 4 min |
| the claim's pair, conversions modelled (the prototype) | before, after | 513 | killed: out of memory at 4 GB | 39 s |
| the mutation pair, conversions modelled | after, mutant | default (a trial) | no verdict: time limit, no candidate | 4 min |

What the brief predicted that is no longer so: the nullable `String` parameters (VF-028) are taken, the claim's
`assume` over `salt.equals(...)` compiles, and nothing between the conversion and the cipher stops the check
(`Arrays.copyOf`, `Integer.parseInt`, the base64 helpers and `StringBuilder` are passed). `records/hashpw-gaps.json`
is older than all of that.

What the brief did not predict: "bound 80 and unwind 513 from the claim" turns the technique off. `ties.rs` names
the state past a loop the checker *summarized*; a loop followed to its end is not summarized. The claim's second
assumption says unwind 513 "completes every loop on this domain", and that is exactly why. Step 6's "by the same
technique" therefore has two honest readings: record that the loop ties do not transfer at the claim's unwinding
(the brief's Done-when allows the record), or relate the two sides one level up, at the call, which the claim's
fourth note and target.json's task note both allow in words.

## 2. The unchanged callee, from its bytecode

`records/callee-footprint/footprint.py` reads the class files itself and follows where references come from
through the callee's closure. It is a record of what a rule's side conditions have to find true, and is no part of
the verifier. `records/callee-footprint/hashpw-bytes.json` is its output for `BCrypt.hashpw(byte[], String)` on the
three class files (before's is the published 5.2.0.M4 class, sha256 `0b137406…`):

- **The same code.** 13 methods reached, each the same instructions in before, after and the mutant; the class
  initializer too (4,976 instructions, no call, five `putstatic`s). `hashpw(String, String)` is the only method
  of the class that differs. No virtual or interface call into application code, no `invokedynamic`, no monitor.
- **Static state.** It reads `P_orig`, `S_orig`, `bf_crypt_ciphertext`, `base64_code` and `index_64`: all final
  arrays of the class, written by the initializer alone, and in the closure only cloned, indexed for a read, or
  asked their length. Their contents after initialization are the same in all three (hashes under `tables`).
  A `final` array's cells can still be written by other code; nothing in this class does, and the class has no
  method like the fixture's `poke`.
- **Writes.** Every array store and field store in the closure lands in an object the call made (the `BCrypt`
  it constructs, the clones of the tables, its local arrays): `entryWrites.callerVisible` is empty. The password
  array is handed to `Arrays.copyOf` (which reads it) and is never stored to; the salt is a String.
- **Outcomes.** A new String from `StringBuilder.toString()`, or one of ten `athrow` sites, all
  `IllegalArgumentException`, or an exception the JVM raises itself. 307's expectations contain one of the last
  kind: `ArrayIndexOutOfBoundsException` for the empty password under `$2$05$`, from inside the key schedule. A
  rule that takes a callee's possible exceptions from its `athrow`s would leave it out.
- **Left open by the record** (its `open` list): what the JDK does with what it is given, which implicit
  exceptions are reachable, termination.

Read with the pair's own conventions (`lib/src/pairing.rs`): each version starts from a fresh state of the statics
and of class initialization, and the previous version is a relocated copy (`before.…BCrypt`) with its own tables.
So "the same static state at both calls" is not one object read twice; it is two copies with the same initializer
run from the same fresh state, which is what the fingerprint of the initializer and its reach has to carry. The
challenge stream's I010 and the expert's review (I012) both say the reach must be closed first; the initializer
here calls nothing, so it is closed once it is in the reach at all.

A shape for the rule, offered as a starting point and nothing more. It is the loop tie one level up: the outcome
of a call is named by everything the call can read.

- The key: the callee's fingerprint over a closed reach, initializers included; each argument (an array by its
  length and cells, a String by its content, nullness, and which arguments are one object); the content of every
  static the reach reads, as the path has it; the classes' initialization.
- The outcome for a key: a result or an exception or neither, the same for the same key. A result is equal
  content in a new object each time, never one object (`twice` in the countermodels). An exception is any class,
  the JVM's own included.
- Refused, by name, unless shown from the bytecode: a write to anything the caller can still see, a static
  written, a call the reach does not close.
- With the conversions modelled as one function (section 3), both sides' byte arrays are the same circuit, so the
  keys are equal without a solver call. The miniature shows this already works for loop ties: `same` in
  `lib/tests/fixtures/callee-countermodels` is verified today with 255 values tied.

`lib/src/shared.rs` has the precedent under JBMC (a memo table per shared callee: seen arguments give the outcome
they gave, new ones an arbitrary one, a witness through it replayed as written). Under the checker's own engine a
shared callee is today one circuit by hashing, which is the thing that cannot be built here.

## 3. The conversions

`records/conversion/` is the evidence for modelling `getBytes("UTF-8")` as the other overload on the pinned JDKs,
which is the reading VF-038 and the user's D029 give the claim:

- `jdk-21.0.13.json`, `jdk-25.0.5.json`: on each runtime (identified by the SHA-256 of its `lib/modules`),
  4,306,308,976 Strings, no difference between `getBytes("UTF-8")`, `getBytes(UTF_8)` and UTF-8 written out in
  the program, nor between `getBytes(US_ASCII)` and US-ASCII written out. That is every String of one and of two
  UTF-16 units (every context a unit's encoding depends on), three to five units over 21 boundary units, runs of
  every length to 200 with each surrogate shape at each position, and four million random ones. Two overloads
  that share an implementation are not independent of each other; the written-out encoder is.
- The same files hold the bytecode of both overloads and of `lookupCharset`: each overload ends in the one
  `encode(Charset, byte, byte[])`, and `Charset.forName("UTF-8")` gives the object `StandardCharsets.UTF_8` is.
  The standard provider is asked before any other (`Charset.lookup2`), so nothing on a class path answers for
  that name.
- `jdk-*-compat.json`: the same without the two-unit part under `-Dfile.encoding=COMPAT` and `LC_ALL=C`, where
  the default charset is US-ASCII: neither conversion depends on the default. (I008's mutant does; it is the
  `defaulted` pair of the fixtures, and stays the user's question, D028.)
- `UTF8` and `unicode-1-1-utf-8` resolve to the same object: an alias is a positive control, not a wrong
  conversion.

`lib/tests/fixtures/conversion-countermodels` holds twelve pairs with what a JVM says of each, a harness
(`check.py`), the test to add, and `prototype-model.patch`. On the prototype the six pairs a model decides come
out right in 7 s; on a prototype made wrong on purpose (any name taken for UTF-8, a surrogate pair as two `?`)
five pairs are falsely verified and the harness says so. The US-ASCII detail is easy to miss: the JDK writes one
`?` for a surrogate pair, so the array is shorter than the String.

Null handling the model must keep: a null password is a `NullPointerException` at the call in both revisions,
before any salt is looked at (also with a null salt); a null charset name is one too, from `lookupCharset`, before
the String is read.

## 4. The mutant

`records/mutant-witness.json`: eight candidate inputs through the replay driver and the real cipher, after
against the mutant, on both JDKs. `é` (U+00E9) under `$2a$06$If6bvum7DFjUnE9p2uDeDu` is a witness: after returns
`…pkPD8vBjYu3BG5XbFtncNiWjjTCgZfW`, the mutant `…Zi5H8lHSGbjxrS8SWUAnS6n3PwA.lHy`, which is what `?` hashes to.
The same password under a null or empty salt, a null password, 72 `a`s followed by `é`, and the empty password
under `$2$05$` are not witnesses.

What that means for the check:

- An abstraction gives a candidate wherever the bytes differ. Whether it is a witness is the cipher's to say, on
  a JVM, with the route's artifacts. The expert's review agrees this is sufficient, and that a candidate which
  does not replay is spurious, never a refutation.
- Today a witness through a shared callee that does not replay sends the proof back to "the callees as written"
  (`shared.rs`, `spurious`). As written is bcrypt in full, which is the run that dies. For this callee the
  refinement has to be another candidate, not the callee's body.
- `accept.py`'s `replay` check wants the witness reproduced on a JVM by the harness the job collected, with the
  claim's assumption held on it. A standalone observation like the file above does not count, by design.

## 5. Running it, and having it accepted

- **The route can run 307 without a driver**, and did on 2026-11-15 (`python3 examples/tools/build.py 307 --task
  preservation`, job `20261115-011448-…`). But `examples/tools/targets/runtime.py` (`_parameters`) passes
  `--assume` only for a `prove` task. For `equivalence` it passes the allowed change, the nullable parameters and
  the bounds, so the recorded command of that job has no `--assume`
  (`records/refusals/preservation.json`, `command`). Through the route the pair is compared on every salt, which
  is another statement than the frozen claim's, and a mutant witness there may have a salt outside the seven.
  This is a finding for whoever owns the route, not something 307's driver can paper over.
- **`examples/tools/beside_route.py`'s `Run` does not fit 307 as it is**: it ends unless the claim's assumptions
  name an adapter entry, compiles `preparation.adapters`, and takes JARs from `preparation.artifacts`. 307 has a
  direct entry and a source slice (`preparation.slice`).
- **`accept.py`'s `mutant` check** compares the hash in the step's log with the one the newest mutant replay's
  receipt records for `revision: mutant, role: original`: `54a1f226…` in `receipts/mutant-replay/20261115T004637Z-…`.
  A driver has to build the mutant by the route's slice recipe (`runtime.prepare`) to arrive at those bytes; a hand
  compile gives a class, not that artifact.
- **`accept.py`'s `artifacts` check** reads pinned JARs. For a slice the pinned things are the commit, the files,
  the JDK and flags, and for before the published class it must reproduce. That is a change to the acceptance
  check, which is the evidence stream's: an inbox item, with this as its reason.
- For an established answer the outcome also needs a witness that some input reaches the property
  (`non-vacuous`), and no unfinished unwinding (`complete`). A callee taken as one function should appear in the
  outcome by name with the conditions it was held to, so that the acceptance check can ask for them later.

No job was queued. The two jobs worth queuing exist only once the conversions are modelled and the callee is
related: `preservation` and `mutant-preservation` at the frozen bound, each with a `--work` folder of its own.
Until then a job at the frozen bound repeats the 39 s out-of-memory stop.

## 6. The same boundary in 287

The user asked that convergence be considered for 287 as well. `records/callee-footprint/287-crypt-raw.json` is
the same record for `BCrypt.crypt_raw(byte[], byte[], int, boolean, int, boolean)` in the pinned 6.3.7 and 6.3.8
JARs:

- the nine methods it reaches are the same instructions in both releases, and so is the initializer;
- it writes its receiver's two fields and arrays it made, and no static; the receiver is the `BCrypt` that
  `hashpw` constructs just before the call and does not read afterwards;
- it returns an array it made.

`hashpw(byte[], String, boolean)` differs between the releases by nine instructions put in after its first six
(the 72-byte guard and its `IllegalArgumentException`); 6.3.8's other 199 are 6.3.7's, shifted, which the tool's
decoder confirms instruction by instruction. So past the guard both
releases run the same instructions on the same values, and a call-level relation at `crypt_raw` (an instance
method on a receiver made for the call) would take the key schedule out of 287's proof, where job
`20261117-180758-…` stopped. Two things are particular to 287: its claim's domain has stored hashes of cost up to
31, on which both releases run 2^31 rounds, so "the same outcome" there is about runs that end; and the expert's
review notes that 287's claim rejects an *assumed* cryptographic summary, so the relation has to be one the
checker shows from the bytecode, as above, and says so in the outcome.

## What is where

| Path | What |
|---|---|
| `examples/307-*/records/step-6-probes.json` | the six probes, with the classes' and binaries' hashes |
| `examples/307-*/records/callee-footprint/` | `footprint.py`; `hashpw-bytes.json` (307); `287-crypt-raw.json` |
| `examples/307-*/records/conversion/` | `ConversionDifferential.java`, `run.py`, four results on Temurin 21.0.13 and 25.0.5 |
| `examples/307-*/records/mutant-witness.json` | which candidates are witnesses |
| `lib/tests/fixtures/conversion-countermodels/` | twelve pairs, `check.py`, `prototype-model.patch`, the test to add |
| `lib/tests/fixtures/callee-countermodels/` | ten pairs, `check.py`, what today's checker says of each |

To run again: `python3 -I records/callee-footprint/footprint.py --help`; `python3 -I records/conversion/run.py
JAVA_HOME…` (four minutes a JDK on four threads); `python3 -I check.py --jvmcontract PATH` in each fixture folder
(seconds). None of them is in the default test run, and none adds a row to `lib/tests/costs.json`.

Not done here, on purpose: no change to the claim or to 307's notes and README; no write in any stream's
workspace; no verification job; no model or rule added to `lib/src`. The classes probed were compiled by hand
with the slice's recipe, so every number above is a probe's, and answers nothing about the claim.

Seen on the way and written up in `lib/tests/fixtures/callee-countermodels/README.md`: a witness whose
difference a second run undoes is reported as not reproduced, and a parameter named `b` does not compile in the
generated pair. Neither is a false proof.
