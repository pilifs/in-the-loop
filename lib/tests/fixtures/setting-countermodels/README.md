# Countermodels of an observation bound to the settings it read

The challenge stream of `domain-advances` (2026-11-17), item 5. It targets the evidence stream's `mmnoqopr`, its fix
for `domain-advances-evidence-I008`, which binds an observed class initializer to its settings:
- the default locale and time zone are stated;
- each system property is stated with its value. A property counts if the class path's code read it by name, through
  `System.getProperty`, the JDK's three getters, or the map's `get`, `getOrDefault` and `containsKey`;
- a read of the properties as a whole is refused;
- a class whose constant pool names `System.getenv` or `ProcessBuilder.environment` is refused.

Evidence's next commit, `vqquvmnm` (its fix for I011), also refuses an initialization that changed the JDK's settings
(a property, the locale), and compares every value of a class it initialized besides in full.

The fix holds for what it was made for. At `qxstltmq` (built apart, with the sources touched),
`observed_countermodels.rs` passes, I008's five cases included.

Each initializer below reads a setting that none of that sees, in a way it does not look for. Each is **Verified** at
`vqquvmnm` with the class observed under the setting. All but `kept` were **Verified** at `qxstltmq` too; `kept` was
written after it and run at `vqquvmnm` only. The result states "it read no system property" and nothing of the
setting, and a JVM under another setting gives another value
(`lib/tests/setting_countermodels.rs`, `each_initializer_gives_what_its_setting_says_on_a_jvm`). Without the
observation, each check is refused.

| Entry | The initializer | Observed under | Proved | A JVM under another setting | Why the binding does not see it |
|---|---|---|---|---|---|
| `mapped` | `Optional.of("sc.value").map(System::getProperty).orElse("absent")` | `-Dsc.value=xyz` | `result == 3` | 6 with no `sc.value` | The recorder takes the first frame past the getters as the reader. A lambda's frame is hidden, so that first frame is `java.util.Optional`, a JDK class, and the read counts as the JDK's own |
| `kept` | `System.getProperties().putIfAbsent("sc.value", "absent")`'s return value | `-Dsc.value=xyz` | `result == 3` | 6 | `Recording` does not override `putIfAbsent`, and where the property is set the map is left as it was, so `vqquvmnm`'s check for a changed setting sees nothing. `replace(k, v, v)`, `compute` and `merge` with a function that keeps the value read the same way. At `qxstltmq`, `System.clearProperty`'s return value (`Properties.remove`) was **Verified** too; `vqquvmnm` refuses that one, since the property is no longer set afterwards |
| `looked` | `MethodHandles.publicLookup().findStatic(System.class, "getenv", ...)` | `SC_VALUE=xyz` | `result == 3` | 6 with no `SC_VALUE` | No constant of the class is a method reference to `System.getenv`. The module documents this as a limit ("not seen: a read of the environment by reflection"), but the result does not say it |
| `counted` | `Runtime.getRuntime().availableProcessors()` | `-XX:ActiveProcessorCount=3` | `result == 3` | 5 under `=5`; 30 on this machine | The JVM's flags and the machine are not recorded |
| `rooted` | `new File("").getAbsolutePath()` | `-Duser.dir=/abc` | `result == 4` | 7 under `/abcdef`; any other working directory | The JDK read `user.dir` at startup |
| `encoded` | `"é".getBytes().length` | `-Dfile.encoding=COMPAT`, `LC_ALL=C` | `result == 1` | 2 with no `file.encoding`, the default since JDK 18 | The JDK took the default charset at startup. It says the locale was `en-US` |

Every assumption each result states is true of a JVM under the other setting. The library line of each says the
initializer ran "in a JVM whose default locale was en-US ... and default time zone Etc/UTC; it read no system
property". The only part of it that is false is "taken to leave that state in every run". That is the same catch-all
that I004's `lowered` and `configured` came under, which `lzpqszyo` and `mmnoqopr` replaced with a stated setting or
a refusal.

The commands, with the fixtures compiled into `C` (`javac -g -parameters --release 21`). The setting reaches the
observer's JVM through the environment, as in evidence's own test:

```
JAVA_TOOL_OPTIONS=-Dsc.value=xyz jvmcontract prove 'sc.M#mapped' --assert 'result == 3' \
  --observed-initializer sc.Mapped --engine native --jbmc /nonexistent/jbmc --details --classes C --classpath C
```

The other five are the same, with the entry, class, assertion and setting of their row.

## Tried and not run

- Not run, of the same kind: `System.currentTimeMillis()`, `nanoTime()`, `Math.random()`, `new Random()`,
  `ProcessHandle.current().pid()` and `UUID.randomUUID()` in an initializer. Each is a value no two runs share,
  observed once. They were left out only because a test of them is not deterministic.
- Not run: `System.setProperties(null)`, after which the JDK rebuilds the properties from the command line into a map
  that is not `Recording`. A property read after it is not recorded.
- `mmnoqopr`'s own cases are guarded, with the guard of each:
  - supertypes are compared (the `isAssignableFrom` skip is gone);
  - the map's keyed reads and the whole-map reads are recorded;
  - the zone is stated;
  - `getenv` named in the constant pool is refused, including through a method reference (`System::getenv` is a
    method handle constant over the same method reference).
- `Properties.getProperty(key, default)` calls `getProperty(key)`, which is overridden, so it is recorded.
- `new Properties(System.getProperties())` reads its defaults through `getProperty`, which is recorded.

## What the checker should say instead

This is the evidence stream's to decide, since `observed.rs` and `ObservedInitializer.java` are its own. State's
`uxomquou` takes the binding whole, so the same holds there until it diverges; it was not run there. Options:

- **The reader's frame**: walk past hidden frames and the JDK's frames to the first class of the class path. A read
  under a JDK frame that a class path frame called is still the class path's. This closes `mapped` and the same read
  through a stream, a `Supplier` or `computeIfAbsent`.
- **The map**: override every method of `Hashtable`/`Properties` that returns or passes on a value (`putIfAbsent`,
  `replace`, `compute*`, `merge`, `remove`, `put`, `equals`, `hashCode`). Each is either recorded by key or refused as
  "as a whole". Or refuse an initializer that calls any method of `Properties` the observer does not record.
- **The JDK's startup settings**:
  - state, or refuse on a difference from the default, the ones a class path initializer can see through the JDK
    without reading a property: `user.dir`, `file.encoding` and `native.encoding`, `line.separator`, and the
    processor count and maximum heap (`availableProcessors`, `maxMemory`);
  - or refuse an initializer whose class or reached code calls `Runtime.availableProcessors`/`maxMemory`/
    `totalMemory`/`freeMemory`, `File.getAbsolutePath`/`getCanonicalPath`/`Path.toAbsolutePath`,
    `Charset.defaultCharset`, `String.getBytes()` or `new String(byte[])` without a charset, `System.currentTimeMillis`/
    `nanoTime`, `Math.random`, `Random.<init>()`, `ProcessHandle`, `UUID.randomUUID` or `InetAddress`.
- **The environment by reflection**: refuse an initializer whose class calls `MethodHandles.Lookup.find*`,
  `Class.getMethod`/`getDeclaredMethod` or `Method.invoke`, or state "it read the environment only through the two
  methods named" in the result.

The test the checker would pass after the fix, to be added to `lib/tests/setting_countermodels.rs` with the fix. It
fails on all six at `vqquvmnm`. A case passes if the check is refused, or if the result names the setting by the word
given:

```rust
/// The checker's side: each class observed under the setting of the test above is proved to give that setting's
/// value, though the result states nothing of the setting and a JVM under the other gives another. A binding that
/// sees the read refuses the observation or states the setting with its value.
#[test]
fn an_observation_is_bound_to_every_setting_its_initializer_read_however_it_read_it() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (entry, class, assert, options, env, said) in [
        ("mapped", "sc.Mapped", "result == 3", "-Dsc.value=xyz", &[][..], "sc.value"),
        ("kept", "sc.Kept", "result == 3", "-Dsc.value=xyz", &[][..], "sc.value"),
        ("looked", "sc.Looked", "result == 3", "", &[("SC_VALUE", "xyz")][..], "SC_VALUE"),
        ("counted", "sc.Counted", "result == 3", "-XX:ActiveProcessorCount=3", &[][..], "processors"),
        ("rooted", "sc.Rooted", "result == 4", "-Duser.dir=/abc", &[][..], "/abc"),
        ("encoded", "sc.Encoded", "result == 1", "-Dfile.encoding=COMPAT", &[("LC_ALL", "C")][..], "charset"),
    ] {
        let mut cli = Command::new(env!("CARGO_BIN_EXE_jvmcontract"));
        cli.env_remove("SC_VALUE").env("JAVA_TOOL_OPTIONS", options);
        for (k, v) in env {
            cli.env(k, v);
        }
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels").join(entry);
        let out = cli
            .args(["prove", &format!("sc.M#{entry}"), "--assert", assert, "--observed-initializer", class, "--engine", "native", "--jbmc", "/nonexistent/jbmc", "--details", "--classes"])
            .arg(classes)
            .arg("--classpath")
            .arg(classes)
            .arg("--work")
            .arg(work)
            .output()
            .unwrap();
        let text = String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr);
        eprintln!("--- {entry}\n{text}");
        if text.contains(&format!("sc.M#{entry} satisfies")) && !text.contains(said) {
            wrong.push(entry);
        }
    }
    assert!(wrong.is_empty(), "proved under a setting the result does not state: {wrong:?}");
}
```

## Audit

The only accepted results that rest on an observation are 290's `fixed-security` and `preservation`. They observe
five classes in each release: `ClassUtils`, `AntPathMatcher`, `UrlPathHelper`, `GenericServlet` and `HttpServlet`.
The JARs are spring-core and spring-web 5.3.28 and 5.3.29, and jakarta.servlet-api 4.0.4, with the hashes checked
against `target.json`. Read with `javap -c -p`:

- None of the five initializers calls any method of the table, nor `Optional`, `MethodHandles`, `Properties` or
  `System` at all.
- The servlet classes call `ResourceBundle.getBundle`, which reads the locale, and the locale is stated.
- `UrlPathHelper`'s initializer calls `LogFactory.getLog`, which reaches `java.util.logging`'s `LogManager`. That
  reads its own configuration through JDK frames, the way `mapped` reads. The observation holds nothing of the logger
  (`logger` is `{"u": "an object of ...LogAdapter$JavaUtilLog"}` in preservation's probe), and a read of a value it
  does not hold is refused.

Not affected, and nothing for the watcher.
