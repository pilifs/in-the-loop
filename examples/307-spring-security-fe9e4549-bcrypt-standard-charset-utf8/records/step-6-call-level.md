# Example 307, step 6: a prototype of the relation at the call, and what it showed

Written 2026-11-17 by the session the user brought in ahead of the preservation stream's step 6, after
[`step-6-packet.md`](step-6-packet.md). The stream is writing its own call-level rule; this is evidence and a
patch to compare against, not a second implementation. Nothing here is a result of the example: the prototype
checks none of the side conditions a rule needs, and two of the fixtures' countermodels show it.

Every run is in [`step-6-call-level-probes.json`](step-6-call-level-probes.json): capped probes (4 GB, 300 s, one
at a time) at the claim's frozen parameters (unwind 513, bound 80, both parameters nullable).

## In short

1. **Both of 307's tasks close with the relation at `crypt_raw`, on JDK 25, under the claim's own assumption.**
   `preservation`: verified in 79 s, 878 MB. `mutant-preservation`: a violation in 58 s, replayed on a JVM
   (a password of supplementary and other non-ASCII units under `$2a$06$If6bvum7DFjUnE9p2uDeDu`). Without a
   relation the same runs die at 4 GB in under 40 s.
2. **With the relation at `hashpw(byte[], String)` the preservation task closes too (53 s, 559 MB), but only on
   JDK 21 since the stream's I010 fix**, and the mutant does not close there under the claim's assumption.
3. **Why JDK 25 differs:** `hashpw(byte[], String)` calls `Integer.parseInt(String)`. The checker follows
   `Integer`'s own bytecode, and JDK 25's `parseInt(String, int)` builds its messages with
   `String.format(String, Object[])`, which `shared::reach` (after kskmpmny) cannot rule out as a way back into
   the application. The callee's code then has no fingerprint, a state at its entry has no key, and a rule keyed
   on either declines without saying so. JDK 21's `parseInt` uses a `StringBuilder` and stays closed. `crypt_raw`
   calls no `parseInt`. The fixture row `parsed` (below) shows this in a fraction of a second.
4. **Why the mutant needs `crypt_raw`, or a search by cases:** at `hashpw(byte[], String)` the abstraction lets
   the callee differ on any two byte arrays, including under a null or malformed salt, where the real callee
   throws the same exception whatever the bytes. The first candidate is then a non-ASCII password with
   `salt = null`, which a JVM rejects, and the run ends with no verdict. At `crypt_raw` the salt's parsing runs as
   written on both sides, only a well-formed salt reaches the abstraction, and the first candidate is real.
   Fixing one valid salt in the assumption does the same at either boundary (a witness under a narrower
   assumption is a witness of the claim once a JVM has replayed it).
5. **A relation by formula alone was enough for both tasks here.** Relating two calls by the content of their
   arguments (equal bytes, then equal outcomes, where the formulas differ) removed the candidate with equal
   bytes (80 units of U+0014) but was not what made either task close. It is also where the prototype is most
   wrong: see the fixtures.

## The prototype

[`prototype-one-function.patch`](../../../lib/tests/fixtures/callee-countermodels/prototype-one-function.patch)
is a diff of about 240 lines to `lib/src/bmc/mod.rs`, against the stream's kskmpmny (git `10b5d9c0cf06`) with
[`prototype-model.patch`](../../../lib/tests/fixtures/conversion-countermodels/prototype-model.patch) applied
first. The stream's working copy has since changed `bytes.rs` and `mod.rs`, so expect to read it, not apply it.

- `JVMCONTRACT_PROTOTYPE_ONE_FUNCTION='owner#name#descriptor ...'` names callees. In a pair of versions, a call
  of one is not run. `Engine::step` sees the callee's frame at its first instruction, takes
  `Engine::state_key` of the path there (the callee's code with what it reaches, its arguments and what they
  reach, the statics that code uses, the classes' initialization), and names the outcome by that key through
  `Ties::bits`: four bits for which of eight exception classes or a return, a length and 64 units for the
  result (a new String, or a new `byte[]` of the low bytes). A second call from a state of the same key, on
  either side, takes the same bits. A state with no key runs the callee as written.
- `JVMCONTRACT_PROTOTYPE_ONE_FUNCTION_BY_CONTENT=1` also adds, for two calls of one callee with different keys,
  "arguments equal by content, then the same outcome".

What it leaves out, each a side condition a rule must check and the prototype takes on trust:

| Left out | What 307 gives for it | The fixture row that fails without it |
|---|---|---|
| What the callee writes to its arguments and receiver | `crypt_raw` writes `P` and `S` of the receiver `hashpw` made, which `hashpw` never reads again; nothing else a caller sees (`callee-footprint/hashpw-bytes.json`, `entryWrites`) | `wiped`: **proved**, falsely |
| Static state the callee writes | none outside `<clinit>` (`statics`) | `counted`: **proved**, falsely |
| The exceptions a callee can throw | the list is eight classes written into the patch; 307 expects `IllegalArgumentException` and one `ArrayIndexOutOfBoundsException` | none yet; `caught` shows an exception is shared like a result |
| The result's type, nullness and size | a non-null `byte[]` of 24, or a String of at most 60 units | none |
| By content: the code, the statics read, aliasing between arguments | the same on both sides in 307 | `table`, `seeded`, `helped`, `aliased`: each **proved**, falsely, with the relation by content, and not with the relation by formula, whose key holds all four |
| That the callee ends | bcrypt's loops are bounded by the cost | none |

So the fixture's rows tell the two prototypes apart from a rule with its conditions: by formula it is wrong on
two rows, by content on six.

## The runs on 307

| Relation at | By content | JDK | `preservation` (claim pair) | `mutant-preservation`, the claim's seven salts | the mutant, one valid salt |
|---|---|---|---|---|---|
| none (the packet's probes) | | 25 | killed at 4 GB, 39 s | stops at `US_ASCII` without a model | |
| `hashpw(byte[], String)`, before the I010 fix | no | 25 | **verified**, 54 s, 558 MB | no verdict, 3 s: candidate with equal bytes, `salt = null` | |
| `hashpw(byte[], String)`, kskmpmny | no | 25 | killed at 4 GB, 38 s | killed at 4 GB | killed at 4 GB |
| the same | no | 21 | **verified**, 53 s, 559 MB | | **violation**, 29 s |
| the same | yes | 21 | **verified**, 56 s | no verdict, 55 s: candidate 80 units of U+FEA0, `salt = null` | **violation**, 42 s |
| `crypt_raw`, kskmpmny | no | 25 | **verified**, 79 s, 878 MB | **violation**, 58 s | |
| the same | yes | 25 | **verified**, 84 s | **violation**, 69 s (64 units of U+FEA0) | |

Every violation is a witness the checker replayed on a JVM, so it stands whatever the prototype trusts. Every
"verified" rests on the conditions in the table above and is a statement about cost and shape only.

Not tried: 287. Its `crypt_raw` has one more parameter and its `hashpw(byte[], String, boolean)` opens at the same
`parseInt` on JDK 25; the packet's section 6 and `callee-footprint/287-crypt-raw.json` have the rest.

## What the stream may want from this

- A test on JDK 25 for whichever boundary it picks. `python3 -I lib/tests/fixtures/callee-countermodels/check.py
  --jvmcontract PATH --only same parsed` takes a second: on kskmpmny `parsed` is verified on JDK 21 and has no
  verdict on JDK 25.
- If the boundary is `crypt_raw`: the receiver is an argument the callee writes. In 307 and 287 `hashpw` makes it
  just before the call and never reads it after; a rule can require that (no use of the receiver
  after the call on any path) or put the written fields in the outcome.
- If the boundary stays `hashpw(byte[], String)`: the reach has to be closed on JDK 25 (a JDK call that is inert
  at its call site, as `Integer.parseInt(String)` is, need not be closed inside, since nothing the application
  made goes in), and the mutant needs either a search by salt or the callee's early checks as facts.
- The mutant's refutation needs no relation by content at `crypt_raw`. If the stream adds one anyway, it has to
  compare what the key by formula holds: the code, the statics, and which arguments are one object.
