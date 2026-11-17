# Countermodels of three rules that landed on 2026-11-17

The challenge stream of `domain-advances`, item 5, on three commits of the other streams:
- the state stream's gap refusal (`qysmsruu`), the fix for `domain-advances-state-I004`;
- the evidence stream's binding of an observation (`lzpqszyo`), the fix for `domain-advances-evidence-I004`;
- the preservation stream's model of a line logged at WARNING (`unswkkxp`), for 287's preservation.

Each rule lets one thing stand in for another, so each fixture asks what the stand-in leaves out:
- an object of the declared class stands in for the JDK's object;
- an observation stands in for an initializer;
- a normal return stands in for the default handler.

Each was **Verified** on the line that added it, built apart from `lib/` at that commit, where a JVM says otherwise.
`lib/tests/rule_countermodels.rs` (`each_fixture_is_what_a_jvm_says_it_is`) holds the fixtures to a JVM. The checker's
side is below, one test per stream: each fails on its stream's line today, as it should.

## `wd`: an assumed object of exactly its declared class (the state stream, `qysmsruu`)

Under `--gaps assume` a JDK method that returns an object "returns a new object, never null: it throws nothing and
changes neither its receiver nor its arguments" (`gaps.rs`). The engine makes it `alloc(path, name)`, where `name` is
the class the *descriptor* declares. `qysmsruu` refuses the gap when that class is one whose model the check runs. A
method declared to return `Object` (`clone()`) slips past the refusal, and the object is then of class `Object`, which
the JDK's object is not:

| Method of `wd.Widened` | A JVM | The checker, `--gaps assume` | What it states |
|---|---|---|---|
| `setCloned()`: `set.clone() instanceof HashSet`, `--model java.util.HashSet` | 1 | **Verified** `result == 0` | `HashSet.clone()` "returns a new object, never null…": true of the JDK |
| `setClonedSize()`: `((HashSet) set.clone()).size()`, -1 on a `ClassCastException` | 1 | **Verified** `result == -1` | the same |
| `dateCloned()`: `new Date(0L).clone() instanceof Date`, no model | 1 | **Verified** `result == 0` | the same of `Date.clone()`, and that `Date(long)` "keeps nothing of its arguments" |

Every assumption the first two state is true of the JDK. The third reproduces on this line (`zwrpkwnl`) too, without
any model, so the hole is older than the run: the approximation says nothing of the object's class, but the engine
makes one. With the model's class, the state stream's refusal is skipped only because the declared class is wider.

The commands, with the fixtures compiled into `classes`:

```
jvmcontract prove --classes classes --classpath classes 'wd.Widened#setCloned' --assert 'result == 0' \
  --engine native --gaps assume --model java.util.HashSet
jvmcontract prove --classes classes --classpath classes 'wd.Widened#dateCloned' --assert 'result == 0' \
  --engine native --gaps assume
```

**Options, for the state stream:**
- Mark an assumed object's class unknown: refuse `instanceof`, `checkcast`, `getClass()` and a virtual call on it by
  name. A call through its declared class is a gap anyway.
- Or refuse a gap whose declared return class is not final: its object's class could be another.
- Either way, refuse it where the declared class is a supertype of a class whose model the check runs. That is the
  `qysmsruu` refusal widened from equality to subtyping.

```rust
/// The checker's side, for the state stream (`qysmsruu`): under `--gaps assume`, no proof that a JDK call's object
/// is of no class but the one its descriptor declares. A JVM says each copy is its receiver's class (the test above).
#[test]
fn an_assumed_objects_class_is_not_taken_to_be_its_declared_one() {
    use jvmcontract::bmc::gaps::GapMode;
    use jvmcontract::{property, Engine, Verdict};
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (method, assertion, model) in [("setCloned", "result == 0", Some("java.util.HashSet")), ("setClonedSize", "result == -1", Some("java.util.HashSet")), ("dateCloned", "result == 0", None)] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("wd.Widened#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.gaps = GapMode::Assume;
        o.assert = Some(assertion.into());
        o.requested_models = model.into_iter().map(String::from).collect();
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels").join(method));
        let out = property::run(&o).unwrap();
        eprintln!("--- {method}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(method);
        }
    }
    assert!(wrong.is_empty(), "proved that a JDK copy is not of its receiver's class, which a JVM says it is: {wrong:?}");
}
```

On `qysmsruu` it fails on all three.

*Tried, and weaker:* a method that returns its receiver (`StringBuffer.append`) is proved to return another object,
but the result states "returns a new object", which is false of the JDK there, so the reader is told.
`Object.getClass()` is the same: assumed to return a new object.

## `ob`: an observation bound to what it was observed on (the evidence stream, `lzpqszyo`)

The binding compares each class the initialization also initialized with that class initialized alone, records the
system properties the class path's code read through `System.getProperty` and the getters that call it, and states
the default locale. What it leaves out:

| Entry point of `ob.M` | Observed | A JVM (UTC, nothing set) | The checker | What the result states |
|---|---|---|---|---|
| `inherited()`: `int k = Derived.k; return Base.x;`, `Derived extends Base`, `Derived.<clinit> { Base.x = 1; k = 7; }` | `ob.Derived` | 1 | **Verified** `result == 0` | nothing false: the supertypes are left out of the comparison (`k.isAssignableFrom(c)` in the observer), and `Base` is initialized by the checker before `Derived`'s state is taken |
| `filled()`: `int k = Filled.k; return Table.T[0];`, `Filled implements Table`, `Table.T = {0}`, `Filled.<clinit> { T[0] = 5; k = 7; }` | `ob.Filled` | 5 | **Verified** `result == 0` | nothing false: a superinterface is left out the same way |
| `bypassed()`: `VALUE = System.getProperties().get("ob.value")`, else `"absent"` | `ob.Bypassed`, `-Dob.value=xyz` | 6 | **Verified** `result == 3` | "it read no system property": false. `Recording` overrides `getProperty(String)` alone, and `Hashtable.get` bypasses it |
| `zoned()`: `OFFSET = TimeZone.getDefault().getRawOffset() / 3600000` | `ob.Zoned`, `-Duser.timezone=Asia/Tokyo` | 0 | **Verified** `result == 9` | "it read no system property": the JDK read `user.timezone`, and the JDK's reads are not listed; the time zone is not stated |
| `environ()`: `VALUE = System.getenv("OB_VALUE")`, else `"absent"` | `ob.Environ`, `OB_VALUE=xyz` | 6 | **Verified** `result == 3` | nothing of the environment |

The first two are the outside review's countermodel (`A.<clinit> { B.x = 1; k = 7; }`, which `lzpqszyo` now refuses),
with `B` a supertype. The last three are of the kind of `lowered` and `configured` (`observed-countermodels`), through
settings the binding does not list. The result still says "it is taken to leave that state in every run (it reads
nothing a run could have changed before it…)", but the binding was made because that sentence did not cover `lowered`
and `configured`, and it covers these no better.

**Options, for the evidence stream:**
- Compare the supertypes too: each superclass and superinterface the JVM initialized, after the observed class against
  alone, as the other classes are.
- Record the properties at the map: override `get`, `getOrDefault`, `entrySet` and the rest, or take a copy of the
  properties before and refuse where the class path's code reached `System.getProperties()` at all.
- State the time zone and the environment the observer had (`TimeZone.getDefault().getID()`, and `System.getenv()` or
  only the variables read), or refuse an observation whose class path code calls `System.getenv` or
  `TimeZone.getDefault`.

```rust
/// The checker's side, for the evidence stream (`lzpqszyo`): an observation is bound to what it was observed on. An
/// initializer that wrote a supertype's static or a superinterface's array is refused or its write carried; one that
/// read a property through the `Properties` map, the default time zone or the environment is refused or the result
/// says so. A JVM in UTC with neither setting gives inherited() 1, filled() 5, bypassed() 6, zoned() 0, environ() 6.
#[test]
fn an_observation_is_bound_to_its_writes_outside_the_class_and_to_every_setting_it_read() {
    use jvmcontract::{property, Engine, Verdict};
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let work = |name: &str| PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels").join(name);
    let mut wrong = Vec::new();
    for (entry, class, assertion) in [("inherited", "ob.Derived", "result == 0"), ("filled", "ob.Filled", "result == 0")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("ob.M#{entry}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.observed_initializers = vec![class.into()];
        o.work = Some(work(entry));
        let run = property::run(&o);
        eprintln!("--- {entry}: {run:?}");
        if matches!(run, Ok(ref out) if out.verdict == Verdict::Verified) {
            wrong.push(entry.to_string());
        }
    }
    // The observer's JVM takes its settings from the environment: JAVA_TOOL_OPTIONS and OB_VALUE stand for a machine
    // or a launcher that sets them.
    for (entry, class, assertion, env, said) in [
        ("bypassed", "ob.Bypassed", "result == 3", ("JAVA_TOOL_OPTIONS", "-Dob.value=xyz"), "ob.value"),
        ("zoned", "ob.Zoned", "result == 9", ("JAVA_TOOL_OPTIONS", "-Duser.timezone=Asia/Tokyo"), "Asia/Tokyo"),
        ("environ", "ob.Environ", "result == 3", ("OB_VALUE", "xyz"), "OB_VALUE"),
    ] {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env_remove("JAVA_TOOL_OPTIONS")
            .env_remove("OB_VALUE")
            .env(env.0, env.1)
            .args(["prove", &format!("ob.M#{entry}"), "--assert", assertion, "--observed-initializer", class, "--engine", "native", "--jbmc", "/nonexistent/jbmc", "--details", "--classes"])
            .arg(classes)
            .arg("--classpath")
            .arg(classes)
            .arg("--work")
            .arg(work(entry))
            .output()
            .unwrap();
        let text = String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr);
        eprintln!("--- {entry}:\n{text}");
        if text.starts_with("✓") && !text.contains(said) {
            wrong.push(entry.to_string());
        }
    }
    assert!(wrong.is_empty(), "proved from an observation that does not say what it rests on: {wrong:?}");
}
```

On `krptozvm` (which holds `lzpqszyo`) it fails on all five.

## `lg`: a record "confined to itself" logged at WARNING (the preservation stream, `unswkkxp`)

`Logger.log(record)` of a Logger the engine made is a normal return that does nothing, under the stated assumption
that the root's one `ConsoleHandler` writes the record to `System.err` and "reports to its ErrorManager, without
throwing, an exception its formatting throws". That holds for a record whose class is `LogRecord`, or an application
subclass that `Engine::confined_record` finds "can do nothing a check observes". It looks for no static write, no
array store, and only reads of final statics, writes of fields of its own classes, and calls of its own classes,
`LogRecord`, `Object`, `String`, `StackTraceElement` and `Throwable`'s constructors and getters. The formatting calls
the getters, and they write and throw within those limits:

| Entry point of `lg.M` | A JVM | The checker (strict) | The hole |
|---|---|---|---|
| `seen()`: `Counted r = new Counted(WARNING, "x"); log.log(r); return r.seen;`, where `Counted.getMessage()` does `seen++` | 1 | **Verified** `result == 0` | a field of its own class is a field of the record *the caller holds*, so the write is observed |
| `escaped()`: `log.log(new Thrown(WARNING, "x"))` in a `try`, returning 1, or 0 on a `Throwable`, where `Thrown.getMessage()` throws `new Throwable()` through a generic sneaky throw of its own class | 0 | **Verified** `result == 1` | `StreamHandler.publish` catches `Exception` around the formatting, so a `Throwable` (or an `Error`) leaves `log` |

Every assumption `seen` states is true of the JDK. `escaped`'s "an exception its formatting throws" is true only if a
`Throwable` is not an exception.

**Options, for the preservation stream:**
- Take only records the engine made itself, or a subclass whose getters the formatting calls write no field at all,
  not "only fields of its classes".
- Refuse a getter that can throw anything but an `Exception`: an `athrow` of a value not known to be an `Exception`,
  or a call that declares a `Throwable`.

```rust
/// The checker's side, for the preservation stream (`unswkkxp`): no proof that logging a record left it as it was, or
/// returned, where the default handler's formatting called a getter that wrote the record or threw a `Throwable`.
/// A JVM gives seen() 1 and escaped() 0 (the test above).
#[test]
fn logging_a_record_is_not_taken_to_skip_what_its_formatting_runs() {
    use jvmcontract::{property, Engine, Verdict};
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (method, assertion) in [("seen", "result == 0"), ("escaped", "result == 1")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("lg.M#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels").join(method));
        let out = property::run(&o).unwrap();
        eprintln!("--- {method}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(method);
        }
    }
    assert!(wrong.is_empty(), "proved that the default handler ran none of a record's getters, which a JVM runs: {wrong:?}");
}
```

On `unswkkxp` it fails on both.

## Audit

Which accepted results use each rule, and whether they are affected:
- `wd`: no example task runs under `--gaps assume`. Every task of 286 to 290 and 307 is strict, and the only
  `advised` ones are 147 to 149. Not affected.
- `ob`: 290's `fixed-security` and `preservation` observe five classes:
  - `ClassUtils`, `GenericServlet`, `HttpServlet`, `UrlPathHelper` and `AntPathMatcher`, read from the pinned JARs
    (spring-core and spring-web 5.3.29, jakarta.servlet-api 4.0.4) with `javap`.
  - None of their `<clinit>`s writes a static of another class: every `putstatic` is of the class's own field.
  - None calls `System.getenv`, `TimeZone` or `System.getProperties`. The servlet classes' `ResourceBundle.getBundle`
    reads the default locale, which the binding states.
  - Their supertypes declare no static they write. GenericServlet's interfaces (`Servlet`, `ServletConfig`) have no
    initialized fields.
  - Not affected.
- `lg`: 287's preservation logs through spring-jcl's `LocationResolvingLogRecord`, whose getters cache the caller's
  location in the record's own fields. The record is made inside `LogAdapter.JavaUtilLog` and dropped after `log`, so
  nothing reads it, and its getters throw nothing but what `new Throwable().getStackTrace()` could. Not affected, and
  287's preservation is not accepted yet.

Nothing for the watcher.
