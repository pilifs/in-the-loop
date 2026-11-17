# Countermodels of taking an unchanged callee as one function of its arguments

Written 2026-11-17, ahead of the preservation stream's step 6 (example 307), by a session the user brought in for
it. Nothing here changes the checker. These are the pairs a rule of the form "both versions call the same code on
equal arguments, so the two calls end alike" must not prove, with the positive controls it must, each judged by a
JVM first.

Why such a rule is on the table: 307's two revisions differ only in how `hashpw(String, String)` turns the
password into bytes; both then call `hashpw(byte[], String)`, whose code and everything it reaches is the same in
both (`examples/307-*/records/callee-footprint/hashpw-bytes.json`). At the claim's unwinding that callee is bcrypt
unwound in full, which the checker cannot hold (`examples/307-*/records/step-6-probes.json`). The claim's own note
allows "a checked summary of the unchanged callee ... bound to its actual bytecode".

The fixture is a miniature of that shape. `Hash.digest(byte[] data, String salt)` is a static method that reads a
`private static final int[]` table, keeps its state in an object it makes, runs 600 rounds (601 for some salts)
that no unwinding in use covers, and returns a new String or throws `IllegalArgumentException` for a null or empty
salt. `Entry`'s methods convert a password as 307's new revision does and call it. The callee classes `Hash`,
`Seeded`, `Wiping`, `Counting`, `Pairing` and `Parsing` compile to the same bytes in `old/` and `new/`; `Entry`, `Helped` and
`Seed` differ.

| Method | What differs between the versions | A JVM | The side condition it holds a rule to |
|---|---|---|---|
| `same` | the entry's instructions only: one expression against three statements | agree | none: the positive control, 307's shape |
| `copied` | the new version passes a copy of the bytes that a loop made | agree | none: a harder control; the arguments are equal by content, not one value written twice |
| `twice` | the new version calls twice and compares the two results by `==` and `equals` | agree (two objects, equal content) | none: a control; a shared outcome is equal content, never one object |
| `table` | the new version writes a cell of the callee's table before the call (`Hash.poke`) | differ at `a`/`b` | the static state the callee reads is the same at both calls; `final` on the field says nothing of the cells |
| `seeded` | `Seed.table()`, which `Seeded`'s initializer calls | differ | the code compared includes what the callee's class initializer reaches |
| `helped` | `Helped`'s private helper: 31 against 33 | differ | the code compared includes private helpers |
| `wiped` | the callee clears `data[0]`; the previous version reads the array afterwards, the new one passed a clone | differ | what the callee writes to an argument is part of its outcome |
| `counted` | the callee counts its calls in a static; the new version calls twice | differ | static state the callee writes is part of its arguments and its outcome |
| `caught` | the previous version catches the callee's `IllegalArgumentException` | differ at an empty or null salt | an exception is an outcome, shared like a result, not assumed away |
| `aliased` | the callee takes two arrays; the new version passes one array twice | differ | arguments equal by content are not the same arguments when one side's are one object |
| `parsed` | as `same`, over `Parsing`, whose rounds come through `Integer.parseInt(String)` | agree | none: a control for the JDK the check runs on (below) |

Each difference is one a single call shows, in a JVM of its own (`check.py` runs each input so), as the pair of
versions gives each version a fresh state.

## What was run

```
jvmcontract equivalence --before old --after new --target app.Entry#NAME --nullable password --nullable salt \
  --assume 'salt == null || salt.equals("") || salt.equals("a") || salt.equals("b")' \
  --engine native --max-array-length 2 --jbmc /nonexistent/jbmc
```

at the checker's default unwinding, which the 600 rounds are past. On the preservation stream's `rmvpqswzxlyv`
(git `e461ac1d2c5f`, built apart; its last commit before the I010 fix), JDK 25.0.5, 12 s for the first ten
(`parsed` has its own section):

| Method | Verdict | Note |
|---|---|---|
| `same` | **verified** | 255 values tied across the versions: the loop's ties already relate two calls whose arguments are one circuit |
| `copied` | no verdict | a spurious witness past the loop's invariant, dropped on a JVM: the copy's cells are other formulas, so nothing is tied |
| `twice` | no verdict | the same; the new version's second call is not tied to its first |
| `table`, `seeded`, `helped`, `wiped`, `counted`, `caught`, `aliased` | **violation**, each replayed on a JVM | no false proof |

So today's ties are sound on all seven and prove 307's shape in the miniature. What they do not do is carry it to
307 itself: there the claim's unwinding (513) is within every loop's bound, so no loop is summarized and nothing is
tied, and at the default unwinding the summaries cost what 287's do.

`check.py --rule-landed` also requires `same` verified, so that a rule which refuses every call is not mistaken for
a sound one. A rule should be tried with each of its side conditions switched off in turn: with the condition a row
names off, that row is the one that must turn **verified**, as the stream did for its `mix` countermodels
(`lib/tests/pairing.rs`). If no row turns, the condition has no countermodel here and needs one.

## `parsed`, and the JDK the check runs on

Added later the same day. Example 307's `hashpw(byte[], String)` reads its cost with `Integer.parseInt(String)`,
and the checker runs `Integer`'s own bytecode. On JDK 25 `parseInt(String, int)` builds its messages with
`String.format(String, Object[])`; on JDK 21 with a `StringBuilder`. Since the preservation stream's kskmpmny
(git `10b5d9c0cf06`), `lib/src/shared.rs`'s `reach` takes a JDK call given an `Object` as a way back into the
application, so on JDK 25 the callee's code has no fingerprint and a state inside it has no key. `Parsing` is
`Hash` with that one call.

| Checker | JDK 21.0.13 | JDK 25.0.5 |
|---|---|---|
| rmvpqswzxlyv, before that fix | | `parsed` **verified** (170 tied) |
| kskmpmny | `parsed` **verified** (170 tied) | `parsed` no verdict: a spurious witness past the loop, nothing tied |
| kskmpmny with the prototype below | **verified** | no verdict, the same |

`same` is verified in all five. So a rule that names the callee's code by its fingerprint proves `same` and
silently declines on `parsed` on JDK 25, which is what it will do on 307 at `hashpw(byte[], String)`. A test of
such a rule belongs on JDK 25; on JDK 21 it passes by accident. The other ten rows on kskmpmny are as in the
table above (no false proof, `same` verified).

## Against a prototype of the rule

`prototype-one-function.patch` is a prototype of the relation at the call, written to see whether 307 closes with
it (`examples/307-*/records/step-6-call-level.md` has what it is and the runs on 307). It checks no side
condition, on purpose, so it is also a rule with every condition switched off:

| Prototype | Falsely **verified** | The others |
|---|---|---|
| by formula (the outcome is named by the key of the state at the callee's entry) | `wiped`, `counted` | `same` verified; `caught` a violation; `table`, `seeded`, `helped`, `aliased` no verdict (a spurious first candidate, where today's loop ties give a violation); `copied`, `twice` no verdict |
| by content as well (equal arguments, then equal outcomes) | `table`, `seeded`, `helped`, `wiped`, `counted`, `aliased` | `same` and `copied` verified; `caught` a violation; `twice` no verdict |

Every row whose side condition the prototype lacks turns verified, and no other does. `check.py --rule-landed`
exits 1 on both.

To run it: `JVMCONTRACT_PROTOTYPE_ONE_FUNCTION` lists the callees, separated by spaces, each
`app/Hash#digest#([BLjava/lang/String;)Ljava/lang/String;` (and `Parsing`, `Seeded`, `Helped`, `Wiping`,
`Counting`; `Pairing`'s descriptor begins `([B[B`); `JVMCONTRACT_PROTOTYPE_ONE_FUNCTION_BY_CONTENT=1` adds the
relation by content.

## What this set does not cover

- A callee reached through a JDK interface or a virtual call (I010): `lib/tests/fixtures/tie-countermodels`.
- A callee that does not terminate on one side's arguments. Equal arguments diverge alike, so a rule that shares
  outcomes is right about it, but a claim that says "both return or both throw" is then about runs that end.
- Reflection, method handles, `invokedynamic`: the miniature and 307's callee have none
  (`callee-footprint/hashpw-bytes.json` would fail on an `invokedynamic`).
- Exceptions the JVM raises inside the callee (an index, a null). 307 has one in its expectations:
  `ArrayIndexOutOfBoundsException` for the empty password under the `$2$05$` salt, from inside the key schedule.
  A rule that lists what a callee can throw from its `athrow`s alone (ten sites, all `IllegalArgumentException`,
  in 307's callee) leaves that one out, and would then prove a pair where one side catches it.

## Two things seen on the way, neither a false proof

- **A witness that a second run undoes is dropped.** With `Hash.poke` written as `TABLE[i & 15] ^= 1`, `table`
  ended "counterexample agree(password="", salt="a") does not reproduce: the method returns true in the
  interpreter", though the generated `RegressionPair.agree("", "a")` returns false on a JVM (run by hand on JDK
  25.0.5). With the write as it is now (`+= 7`), the same pair is a violation. A plausible cause, not checked in the
  code: the witness is run more than once in one state, and the second run's write cancels the first. The verdict
  was "no verdict", never a proof. To reproduce, put the `^= 1` back in both versions' `Hash.java`.
- **A parameter named `b` does not compile in the generated pair**: for `String given(byte[] b, String salt)` the
  check ends "the regression claim as Java ... does not compile: variable b is already defined in method
  agree(byte[],String)". `lib/src/pairing.rs` names its own locals `a`, `b`, `ea`, `eb`. 287's and 307's
  parameters are named otherwise.
