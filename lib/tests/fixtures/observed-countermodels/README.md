# Countermodels of an observed class initializer

`prove --observed-initializer CLASS` (`lib/src/observed.rs`, `lib/src/bmc/observed.rs`) gives a class the static
state a JVM left after initializing it, instead of running its `<clinit>`. What the observation does not say: what
the initializer wrote *outside* the class, and what the run it was observed in read (the default locale, a system
property, which class file). Each fixture here depends on exactly one of those. `oc.M.main` runs an entry point on a
JVM (`java -cp app:mr.jar oc.M crossed`), and `lib/tests/observed_countermodels.rs` holds the fixtures to what it
prints. The challenge stream reproduced each on the checker at `yypzyxmw` (2026-11-17).

| entry point | what the JVM says | what the checker proved | what the observation does not say |
|---|---|---|---|
| `crossed()`: `int k = A.k; return B.x;` with `A.<clinit> { B.x = 1; k = 7; }` (`--observed-initializer oc.A`) | 1 | `result == 0`, **Verified** | the write to `B.x`: only `A`'s own fields are taken, and `B` is initialized at its first use as if `A`'s initializer had not run |
| `lowered()`: `Lowered.I.charAt(0)`, `I = "I".toLowerCase()`, observed with `JAVA_TOOL_OPTIONS="-Duser.language=tr -Duser.country=TR"` | 105 in English, 305 in Turkish | `result == 305`, **Verified**, and the result no longer says anything about the default locale (unobserved, the same check states "the default locale's language is not Turkish, Azeri or Lithuanian") | the locale the observer's JVM had, which it takes from the environment |
| `configured()`: `Configured.VALUE.length()`, `VALUE = System.getProperty("oc.value", "absent")`, observed with `-Doc.value=xyz` | 6 where unset | `result == 3`, **Verified** (unobserved: a gap at `System.getProperty`) | the property the initializer read |
| `shadowed()`: `new org.xml.sax.helpers.AttributesImpl().getLength()`, with a JAR on the class path that holds a copy of the class returning 42 (`shadow/`, as xml-apis carries the JDK's XML classes) | 0: a JVM loads a class of a package of a boot-layer module from the module, never the class path | `result == 42`, **Verified**; `result == 0` a violation on a witness whose outcome was 42 | (not an observation: the same hole as the next row, in the class path reader) the class file the check read is not the JVM's |
| `released()`: `mr.Release.get()` from a multi-release JAR (`a = 1; get() = a` in the base file, `a = 2; get() = a * 10` under `META-INF/versions/17`) | 20 | `result == 1`, **Verified**, unobserved; with `--observed-initializer mr.Release`, `result == 2`, **Verified**: the versioned file's state on the base file's code; `result == 20` a violation on a witness whose outcome was 1 | that the observation and the check read two different class files |

The result of each states the observation's assumption ("it is taken to leave that state in every run (it reads
nothing a run could have changed before it, and the objects it leaves are held by no other class)"). That covers
none of the first three: `crossed` does leave the same state in every run, and its objects are its own; the locale and
the property are not something "a run could have changed before it" but the JVM's settings; and the class file is
not the run's at all.

**Refused here** (the class path reader is no stream's this run): `released` and `shadowed`, by
`ClassPath::refused` (`lib/src/classpath.rs`), when the class is loaded or copied for a pair. A class whose first
holder on the class path is a JAR whose manifest says `Multi-Release: true` and which holds a file of it under
`META-INF/versions/N/`: the checker has no verdict on it, and a pair whose previous version has its own copy of the
JAR is an error that names it. A class an entry holds in a package of the JDK's image, unless its class file is the
image's own byte for byte or one of the tool's models (the tool puts both on a class path itself: a contract's
proof against the JDK's bytecode, JBMC's class path): the class is the JDK's to the checker, as to a JVM, and a call
into it the gap it is anywhere else. The enumeration of every class still reads the base file, so that the walks asking
which classes there are see it. *Not covered*: a versioned class whose base declares other methods or another
superclass, seen through that enumeration only (an override the base lacks); resources under
`META-INF/versions/` and resources of a JDK package (`ClassPath::resources`).

**Handed over** (the evidence stream binds an observation, its brief's item 5): `crossed`, `lowered` and
`configured`. The test it should make pass, in `lib/tests/observed_countermodels.rs` beside the others (it fails at
`yypzyxmw` on all three: `crossed` and both CLI runs are Verified with no word of the locale or the property):

```rust
/// An observation is bound to what it was observed on: an initializer that writes another class's static is
/// refused or its write carried, and one observed in a Turkish JVM, or with a property set, is refused or the result
/// says so. On a JVM in English with no `oc.value`, crossed() is 1, lowered() 105 and configured() 6.
#[test]
fn an_observed_initializer_is_bound_to_what_it_was_observed_on() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let proved = |r: Result<property::Outcome, jvmcontract::Error>| matches!(r, Ok(ref o) if o.verdict == Verdict::Verified);
    let mut crossed = proving("oc.M#crossed", "result == 0", "crossed");
    crossed.observed_initializers = vec!["oc.A".into()];
    let crossed_proved = proved(property::run(&crossed));
    // The observer's JVM takes its settings from the environment; JAVA_TOOL_OPTIONS stands for a machine whose
    // default locale is Turkish, or a launcher that sets a property.
    let cli = |settings: &str, target: &str, assert: &str, class: &str, name: &str| {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env("JAVA_TOOL_OPTIONS", settings)
            .args(["prove", target, "--assert", assert, "--observed-initializer", class, "--engine", "native", "--jbmc", NO_JBMC, "--details", "--classes"])
            .arg(&c.app).arg("--classpath").arg(&c.jar).arg("--work").arg(work(name))
            .output()
            .unwrap();
        String::from_utf8_lossy(&out.stdout).to_string()
    };
    let lowered = cli("-Duser.language=tr -Duser.country=TR", "oc.M#lowered", "result == 305", "oc.Lowered", "lowered");
    let configured = cli("-Doc.value=xyz", "oc.M#configured", "result == 3", "oc.Configured", "configured");
    let lowered_unbound = lowered.starts_with("✓") && !lowered.contains("default locale");
    let configured_unbound = configured.starts_with("✓") && !configured.contains("oc.value");
    assert!(!crossed_proved && !lowered_unbound && !configured_unbound, "crossed proved: {crossed_proved}\nlowered: {lowered}\nconfigured: {configured}");
}
```

**Audit** (2026-11-17): the only accepted results that used an observation are 290's `fixed-security` and
`preservation`, on five classes. Read from the pinned, hash-checked JARs (`javap -c`), no `<clinit>` of the five
(`ClassUtils` and `AntPathMatcher` of spring-core 5.3.28/29, `UrlPathHelper` of spring-web 5.3.28/29,
`GenericServlet` and `HttpServlet` of jakarta.servlet-api 4.0.4) writes a static of another class; `GenericServlet`
and `HttpServlet` read the default locale, through `ResourceBundle.getBundle`, into a field the observation does
not hold (a read of it is refused), and `UrlPathHelper` asks commons-logging for a `Log`, also not held. Not
affected by `crossed`, `lowered` or `configured`. Of the examples' pinned JARs only 288's spring-core 6.1.13/14 are
multi-release, with one versioned class (`org.springframework.core.task.VirtualThreadDelegate`, for Java 21), which
no result names; the classes whose constant pools reach it, directly or through each other, are 7 of the JARs'
2441 (`SimpleAsyncTaskExecutor` and its two nested classes, `VirtualThreadTaskExecutor`, `SimpleAsyncTaskScheduler`
and its nested class, and the class itself), and 288's adapter names none of them (`DataBinder`,
`BeanWrapperImpl`, `MutablePropertyValues`, `BindingResult`, `FieldError`), so neither its check nor its pair
reads the class: not affected, and the refusal does not touch it. No pinned JAR of any example (58 of the 68
artifacts in a `target.json` were on this machine, all of 286 to 290's among them) holds a class of a package of the
JDK's image: not affected by `shadowed`.
