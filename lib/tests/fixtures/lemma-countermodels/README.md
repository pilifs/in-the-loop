# Countermodels of a checked summary

`prove --lemmas FILE` proves each lemma first, from the state the harness starts in, and then lets the lemma's
summary stand in for its method's calls in whatever state they are made (`lib/src/summary.rs`). The foundation
refuses a lemma whose method or clauses read what a caller can change, and one whose method changes what a caller
can see (`Engine::reads` and `Engine::keeps` in `lib/src/bmc/mod.rs`). It does not show those refusals complete:
this folder is the challenge stream's attempt to get past them (domain-advances, item 3, 2026-11-17). `lc.M.main`
runs one entry point on a JVM, and `lib/tests/lemma_countermodels.rs` holds the fixtures to what it prints.

## False proofs, reproduced at `llwznzwm`, now refused or refuted

| entry point | what the JVM says | lemma | what the checker proved | what the stand-in did not say |
|---|---|---|---|---|
| `seen()`: `Base.SEEN`, where `Base.SEEN = Derived.limit()` comes before `Base.LIMIT = parseInt("7")` and `Derived extends Base` reads `LIMIT` | 0 | `Derived#limit`: `result == 7` (true once `Base` is initialized) | `result == 7`, **Verified** | the summary was used inside `Base`'s initializer, before `LIMIT` was written: the foundation's guard looked at the method's own class (`Derived`, initialized) only |
| `heldSeen()`: the same with `Holder` and `Reader`, no inheritance; the lemma's assumption `lc.Holder.SEEN >= 0` initializes `Holder` in its proof | 0 | `Reader#limit`: assume `lc.Holder.SEEN >= 0`, `result == 7` | `result == 7`, **Verified** | the same |
| `setThenOwn(5)`: `Settings.value = v; return Own.limit()`, with `Own.LIMIT = Settings.value` | 5 | `Own#limit`: `result == 0` | `result == 0`, **Verified** | the proof ran `Own`'s initializer in the harness's state; a caller initializes `Own` after writing what it reads |
| `turkishThenLowered()`: `Locale.setDefault(tr)`, then `Lowered.lowered()`, with `Lowered.I = "I".toLowerCase()` | 305 | `Lowered#lowered`: `result == 105` | `result == 105`, **Verified** | the same, through the default locale |
| `setThenCopied(5)`: `Table.T[0] = v; return Copied.first()`, with `Copied.FIRST = Table.T[0]` | 5 | `Copied#first`: `result == 0` | `result == 0`, **Verified** | the same, through an array another initializer made; it took the first version of the refusal to find |
| `appendThenLogged()`: `Logged.LOG.append("x")`, then `Logged.logged()`, `LOG.length()` of `static final StringBuilder LOG` | 1 | `Logged#logged`: `result == 0` | `result == 0`, **Verified** | a builder's content is read by the engine's model, which `Engine::reads` was not asked about: the field is final, the builder is not |
| `appendThenLoggedThroughLambda()`: the same through `LENGTH = LOG::length` | 1 | `Logged#loggedThroughLambda`: `result == 0` | `result == 0`, **Verified** | the same, the builder a method reference's captured value |

**Refused here** (summaries are no stream's this run; `lib/src/bmc/mod.rs`, `lib/src/bmc/strings.rs`):

- No summary stands in for a call while any class is being initialized: the call runs as written (`invoke_static`).
  `seen` and `heldSeen` are now violations, as on a JVM, and `derivedLimit()` (7) still uses the lemma.
- In a lemma's proof, a class initializer the proof runs (the method's class and its superclasses, which the
  harness initializes, or a class the assumption uses) is held to what the lemma is held to (`Engine::in_lemma`):
  it reads no static field that is not final, unless of a class being initialized, no field that is not final or
  cell of an object that was there when it started or that another initializer made, and not the default locale.
  The objects there when an initializer starts or returns count as there before the call (`Obj::given`). `own`,
  `lowered` and `copied` are refused, with the initializer named.
- A lemma reads no `StringBuilder` that was there before the call, by any method of the model (`builder_method`).
  `logged` and `loggedThroughLambda` are refused.

*Not covered*: none of this is about a proof by induction alone (`--decreases` without `--lemmas`), which the
summary does not leave: its hypothesis stands in for its calls of itself only, in the state of the call under
proof, which nothing it runs may write.

## Tried and found guarded

| what | entry point (JVM) | guarded by |
|---|---|---|
| an array a lambda captured, also held by a final static field | `setThenBoxed(5)` (5) | `Engine::reads` on an array that was there before the call (`Insn::ArrayLoad`) |
| the ArrayList model's `size()` on a list a final static field holds (`--model java.util.ArrayList`) | `addThenItems()` (1) | the model runs as bytecode: `reads_field` on a field that is not final of an object that was there |
| a static read by reflection | `setThenReflected(5)` (5) | `Class.getDeclaredField` is a gap, refused under `--gaps strict` |
| a lemma about a method that calls itself forever, used for its own calls | `once()` (StackOverflowError) | the summary is not given to its own proof: the proof recurses to the depth limit |
| two lemmas about methods that call each other | `pinged()` (StackOverflowError) | a lemma's proof is given no lemma (`lemmas: None`, `lib/src/property.rs`) |

Read and not built, with why: a `Pattern` is immutable, and the only modelled method of a `Matcher` is
`matches()`, which resets it; any other method makes the Matcher an object the engine knows nothing of
(`lib/src/bmc/regex.rs`). No class of the tool's models (`lib/models/java`) declares a static field that is not
final. `Locale.getDefault()` stays the JDK call it is (a gap, `lib/src/bmc/locale.rs`). An induction whose measure
reads state: its method may write nothing that was there before the call (`Engine::keeps`, in a proof by
induction too), so what the measure reads is the same at each call of itself (`a_proof_by_induction_is_not_of_a_method_whose_calls_of_itself_write_or_throw` in `lib/tests/claims.rs`).

## Audit (2026-11-17)

The only lemma any example uses is `PatternMatchUtils.simpleMatch(String, String)`: 286 (`proofs/simple-match.contract`,
spring-core 5.3.18/19) and 288 (`simple-match.contract`, `simple-match-pair.contract`, spring-core 6.1.13/14). Read
from the pinned JARs (`javap -c -p`), the class declares no static field and no initializer, and the method calls
only `String`'s `indexOf`, `equals`, `length`, `substring`, `endsWith`, `isEmpty` and `startsWith` and itself. Its
proof runs no initializer of an application class and reads no builder, and none of the adapters (`replay/adapter`)
or `DataBinder`'s initializer calls it while a class is being initialized. 286's decided result (denied on 5.3.19,
the decision claim through its adapter) used the lemma and is **not affected**; 288 has no proof verdict.
