# Logging countermodels: an Error a record's getter raises with no `athrow`

The preservation stream's `lqkwokqq` (2026-11-17), its fix for I006, takes `Logger.log(record)` of a record of a
"confined" class as a normal return. This holds where the formatting the default handler runs can do nothing a check
observes beyond the fix's havoc of the record's number fields (`Engine::confined_record` and `Engine::formatted` in
`lib/src/bmc/runtime.rs`). The scan now refuses an `athrow`, and the module gives the reason: "The handler catches
`Exception` around the formatting, and what else can leave a getter is an `Error` the engine does not model or a
`Throwable` an `athrow` throws, which is why there is none."

A JVM raises an `Error` with no `athrow` in the class, and `StreamHandler.publish`'s `catch (Exception)` lets it out
of `log`:

| Entry point of `lh.M` | The record's `getMessage()` | A JVM | The checker at `kskmpmny` (strict) |
|---|---|---|---|
| `huge()`: `log.log(new Huge(WARNING, "x"))` in a `try`, 1 if it returns, 0 on a `Throwable` | `new long[Integer.MAX_VALUE]`, an `OutOfMemoryError` ("Requested array size exceeds VM limit") | 0 | **Verified** `result == 1` |
| `deep()`: the same with `new Deep(...)` | a private method that calls itself without end, a `StackOverflowError` | 0 | **Verified** `result == 1` |

Each class passes the scan: no `athrow`, no field write, no `invokedynamic`, calls only of its own class and of
`LogRecord`. The first version of `huge` concatenated a string, an `invokedynamic`, and was refused.

## Commands

```sh
javac -g -parameters -proc:none --release 21 -d /tmp/lh-c lib/tests/fixtures/log-countermodels/lh/*.java
java -cp /tmp/lh-c lh.M                      # huge=0 deep=0
jvmcontract prove 'lh.M#huge' --classes /tmp/lh-c --engine native --assert 'result == 1'
jvmcontract prove 'lh.M#deep' --classes /tmp/lh-c --engine native --assert 'result == 1'
```

`lib/tests/log_countermodels.rs` holds the fixture to a JVM.

## Options, for the preservation stream

- Refuse an array allocation whose length is not a small constant, and any call that can recurse: a call of a method
  of the record's own classes that reaches itself. That leaves an `Error` only from the JVM's own limits, which a
  stated assumption can name.
- Or state it: "the record's getters raise no `Error`", as the assumption a `log` of an application record rests on.
  An `Error` of a deep stack is possible for any record, `LogRecord`'s own included, if the stack is nearly full when
  `log` is called.

## The checker's side

For the preservation stream, beside `rule_countermodels.rs`'s logging test (`lh` compiled like `lg`):

```rust
/// No proof that logging a record returned, where the record's getter raises an Error with no athrow.
#[test]
fn logging_a_record_is_not_taken_to_return_where_its_getter_raises_an_error() {
    use jvmcontract::{property, Engine, Verdict};
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for method in ["huge", "deep"] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("lh.M#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some("result == 1".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("log-countermodels").join(method));
        if property::run(&o).unwrap().verdict == Verdict::Verified {
            wrong.push(method);
        }
    }
    assert!(wrong.is_empty(), "proved that log returned where a JVM's handler lets an Error out: {wrong:?}");
}
```

At `kskmpmny` the CLI runs above give both the verdict this test fails on (the same options).

## Tried and guarded

- *A getter that writes `LogRecord`'s own fields through its setters* (`setMessage`, `setLoggerName`). The havoc
  covers only the fields of the classes below `LogRecord`, but the checker cannot read `LogRecord`'s state after
  construction: `getMessage()` and `getLoggerName()` are each a gap under strict, `super.getMessage()` included. A
  write there is not observable to a check.
- `lg.M#seen` and `#escaped` (`rule-countermodels`), I006's cases: a violation and a gap at `kskmpmny`, by the
  preservation stream's own test.

## Audit

The only accepted result that logs is 287's preservation, which is open. It logs through spring-jcl's
`LocationResolvingLogRecord`: its getters take a new `Throwable`'s stack trace and allocate nothing sized by input,
and do not recurse. Nothing for the watcher.
