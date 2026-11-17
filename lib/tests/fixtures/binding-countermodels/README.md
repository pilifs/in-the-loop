# Countermodels of an observed initializer's binding

`prove --observed-initializer CLASS` gives a class the static state a JVM left after initializing it, instead of
running its `<clinit>`. Since the evidence stream's `lzpqszyo` the observation is bound to what it was observed on
(`lib/src/observed.rs`): among other things, each class of the class path the initialization initialized besides the
class must be left as it is initialized alone, "as far as the observation holds its fields", and a value it does not
hold is compared by what it is said to be. The state stream's `llyzwmyp` copied the binding onto its line and named
a lambda's hidden class by what it was defined from (`R$$Lambda`), so that two runs of one lambda compare equal.

What the comparison still does not say: what the initializer wrote into a value the observation does not hold (a
lambda, an object of an application class), and what it wrote outside the class path (the JDK's own state, such as
the default locale, which is read before the initialization). Each fixture here depends on exactly one of those.
`bc.M.main` runs all three on a JVM (`java -cp CLASSES bc.M` prints `rehooked=5 boxed=5 relocaled=305`), and
`lib/tests/binding_countermodels.rs` holds the fixture to it. The challenge stream reproduced each on 2026-11-17.

| entry point | the initializer observed | a JVM | the checker, with the observation | without it |
|---|---|---|---|---|
| `rehooked()`: `int k = Rehooked.k; return Hooks.hook.getAsInt();` | `Rehooked.<clinit> { Hooks.install(5); k = 7; }`, where `Hooks.hook = () -> 1` and `install(n)` sets `hook = () -> n` | 5 | `result == 1`, **Verified** at `vvpxytqs` (state) | a violation, outcome 5 |
| `boxed()`: `int k = Boxed.k; return Boxes.BOX.value;` | `Boxed.<clinit> { Boxes.BOX.value = 5; k = 7; }`, where `Boxes.BOX = new Box()` | 5 | `result == 0`, **Verified** at `vvpxytqs` (state) and at `nsnxmlmt` (evidence) | a violation, outcome 5 |
| `relocaled()`: `int k = Relocaled.k; return "I".toLowerCase().charAt(0);` | `Relocaled.<clinit> { Locale.setDefault(Locale.forLanguageTag("tr")); k = 7; }` | 305 | `result == 105`, **Verified** at `vvpxytqs` (state) and at `nsnxmlmt` (evidence) | a violation, outcome 305, run on a JVM |

The commands, from a folder holding the compiled fixture in `classes/`:

```
jvmcontract prove bc.M#rehooked --assert 'result == 1' --observed-initializer bc.Rehooked --engine native --jbmc /nonexistent/jbmc --details --classes classes --work WORK
jvmcontract prove bc.M#boxed --assert 'result == 0' --observed-initializer bc.Boxed --engine native --jbmc /nonexistent/jbmc --details --classes classes --work WORK
jvmcontract prove bc.M#relocaled --assert 'result == 105' --observed-initializer bc.Relocaled --engine native --jbmc /nonexistent/jbmc --details --classes classes --work WORK
```

What each result states, and why that does not cover it:

- `rehooked` and `boxed`: "it initialized bc.Hooks besides, and left each in the state the class has initialized
  alone, as far as the observation holds its fields (what it holds nothing of is taken to be the same too)". That is
  the limit, stated, and here it is false: the observer says `hook` is "an object of bc.Hooks$$Lambda" alone and after
  `Rehooked`, and `BOX` "an object of bc.Box" both times, while the lambda and the box are not the same. The check
  initializes `Hooks` and `Boxes` itself at their first use, as if the observed initializer had not run. The reader
  of the result has no way to tell from it that the initializer wrote into one of those values.
  - `boxed` is older than `llyzwmyp`: it is the binding's from `lzpqszyo` on.
  - `rehooked` is `llyzwmyp`'s: before it the lambda's name carried the JVM's address, which differs from run to run,
    so the binding refused it as a write (the refusal 286's bind met). The lambda `install` makes is of `Hooks`, so it
    is named `bc.Hooks$$Lambda` as `() -> 1` is. A capturing lambda's captured value (`n`) is not compared at all, and
    neither is which of a class's lambdas it is.
- `relocaled`: "in a JVM whose default locale was en-US" and "the default locale's language is not Turkish, Azeri or
  Lithuanian". The observer reads the default locale before it initializes the class (`ObservedInitializer.main`),
  and the classes compared are of the class path only, so an initializer that sets the JDK's default is observed as
  if it had not. Without the observation the checker runs `Locale.setDefault` (it models it) and gets 305. Every
  stated assumption reads as true of the JVM the check is about, which starts in English: the initializer, not the
  JVM's settings, makes it Turkish.

**Options for a fix** (the binding is the evidence stream's, and the state stream holds a copy):

- For values not held: refuse when a class the initialization initialized holds one, as before `llyzwmyp` did for
  lambdas by accident; or hold one level more of it: an object's fields and a lambda's captured values (the hidden
  class's fields read by reflection, with which method it calls), compared as the held values are. Refusing only
  objects reached from a field the initializer's code writes is not enough: `boxed` writes no static.
- For the JDK's state: read the default locale (all three categories) again after the initialization, and refuse
  or state it where it changed. The time zone, the default charset and the properties (`System.setProperty`, which
  the observer's `Recording` takes and then drops when it puts the original properties back) are of the same kind;
  of these only the locale is modelled by the checker, so a change to the others is a gap or refused there.

**Tried and guarded**, on state's `vvpxytqs` (its rule for an object a JDK call returns under `--gaps assume`), in the
same session:

- A JDK call that returns `null` under assume (`TreeMap.get` of an absent key) is proved never null, which the
  result states ("returns a new object, never null"): stated, not a hole of the rule.
- A string concatenation of the object: `String.valueOf(Object)`, which has no approximation under assume, is refused.
- An `aastore` of the object into an array of another element type, a virtual call, a cast and `instanceof`: each
  refused by name (`Engine::of_unknown_class`, and `ArrayStoreException` is refused before).
- A lemma's subclass argument, the effect contract's `linkedAdmin` case for lemmas: a lemma is over primitives and
  Strings only (`summary.rs`), so no argument can be of a subclass.

**The test the owners' checker should pass**, beside `an_observed_initializer_is_bound_to_what_it_was_observed_on`
in `lib/tests/observed_countermodels.rs` (it fails on all three at `vvpxytqs` and on `boxed` and `relocaled` at
`nsnxmlmt`, where `rehooked` is refused for the lambda's address, as it should be):

```rust
/// An initializer that writes beside its own class: into a lambda or an object another class holds, or the JDK's
/// default locale. Each is refused, or the write carried. On a JVM rehooked() is 5, boxed() 5 and relocaled() 305
/// (tests/binding_countermodels.rs).
#[test]
fn an_initializer_that_writes_beside_its_own_class_is_refused_or_carried() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/binding-countermodels/bc");
    let classes = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("binding-countermodels-checked");
    let _ = std::fs::remove_dir_all(&classes);
    let sources: Vec<PathBuf> = std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
    assert!(Command::new("javac").args(["-g", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&classes).args(&sources).status().unwrap().success());
    for (entry, assert, class) in [("bc.M#rehooked", "result == 1", "bc.Rehooked"), ("bc.M#boxed", "result == 0", "bc.Boxed"), ("bc.M#relocaled", "result == 105", "bc.Relocaled")] {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env_remove("JAVA_TOOL_OPTIONS")
            .args(["prove", entry, "--assert", assert, "--observed-initializer", class, "--engine", "native", "--jbmc", NO_JBMC, "--classes"])
            .arg(&classes).arg("--work").arg(work(class))
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&out.stdout);
        assert!(!stdout.starts_with("✓"), "{entry}: proved where a JVM says otherwise\n{stdout}");
    }
}
```

**Audit** (2026-11-17): the only accepted results that used an observation are 290's `fixed-security` and
`preservation`, on five classes (`ClassUtils` and `AntPathMatcher` of spring-core 5.3.28/29, `UrlPathHelper` of
spring-web 5.3.28/29, `GenericServlet` and `HttpServlet` of jakarta.servlet-api 4.0.4). Read with `javap -c` from the
pinned JARs: no `<clinit>` of the five calls `Locale.setDefault`, `TimeZone.setDefault` or `System.setProperty`,
none has a `putfield` or an `invokedynamic`, and each `putstatic` is of its own class. `UrlPathHelper` calls setters
on the two instances it makes, `ClassUtils.hasMethod`, which reads, and spring-jcl's `LogFactory.getLog`, which may
register a logger with the JDK's logging (JDK state, of `relocaled`'s kind); the `Log` it keeps is not held, so a
read of it is refused, and 290's adapters name no logger. `GenericServlet` and `HttpServlet` only load a resource
bundle. Not affected, and nothing for the watcher. 286's protected-state path, which `llyzwmyp` is for, has no decided
answer.
