# Countermodels of a model of `String.getBytes("UTF-8")` and of the US-ASCII conversion

Written 2026-11-17, ahead of the preservation stream's step 6 (example 307), by a session the user brought in for
it. Nothing here changes the checker. It is what a model of the two conversions has to get right, stated as pairs
of versions a JVM has already judged, so that the model can be written against them.

Example 307's two revisions differ by one call: `password.getBytes("UTF-8")` in a handler for
`UnsupportedEncodingException`, against `password.getBytes(StandardCharsets.UTF_8)`. The checker models the second
(`lib/src/bmc/bytes.rs`, `Engine::string_bytes`) and not the first, so 307's `preservation` stops there in a
second. The mutant of `mutant-preservation` converts with `StandardCharsets.US_ASCII`, which the checker does not
read either, so that task stops at the field. Both stops are in `examples/307-*/records/step-6-probes.json`.

`old/app/Text.java` and `new/app/Text.java` hold twelve methods `int NAME(String s, int k)`. Each converts `s` and
returns the byte at index `k`, or 256 plus the number of bytes for an index outside them. Two conversions that
give different bytes so differ at some `s` and `k`, and a check compares one byte and no sum of all.

| Method | Previous version | New version | A JVM (21 and 25) | A check may say |
|---|---|---|---|---|
| `named` | `getBytes("UTF-8")`, with 307's handler | `getBytes(UTF_8)` | agree on every String | **verified** |
| `written` | UTF-8 written out, a lone surrogate as `?` | `getBytes("UTF-8")` | agree | **verified** |
| `asciiWritten` | US-ASCII written out, a surrogate pair as one `?` | `getBytes(US_ASCII)` | agree | **verified** |
| `lone` | UTF-8 written out, a lone surrogate as three bytes | `getBytes("UTF-8")` | differ at `\uD800` | **violation** |
| `paired` | UTF-8 written out, a pair as two three-byte units | `getBytes("UTF-8")` | differ at `😀` | **violation** |
| `asciiPairs` | US-ASCII written out, a pair as two `?` | `getBytes(US_ASCII)` | differ at `😀` | **violation** |
| `alias` | `getBytes("UTF8")` | `getBytes(UTF_8)` | agree (an alias of UTF-8) | verified, or no verdict |
| `ascii` | `getBytes("US-ASCII")` | `getBytes(UTF_8)` | differ at `é` | violation, or no verdict |
| `latin` | `getBytes("ISO-8859-1")` | `getBytes(UTF_8)` | differ at `é` | violation, or no verdict |
| `unknown` | `getBytes("UTF-9")`, the handler returns -1 | `getBytes(UTF_8)` | differ at every String | violation, or no verdict |
| `chosen` | `getBytes(s.length() == 2 ? "US-ASCII" : "UTF-8")` | `getBytes(UTF_8)` | differ at `aé` | violation, or no verdict |
| `defaulted` | `getBytes()`, the platform's default charset | `getBytes(UTF_8)` | agree; differ at `é` under `-Dfile.encoding=COMPAT` with `LC_ALL=C` | no verdict, or one under a stated assumption about the default |

The first six are the ones a model of the two conversions decides. The next five are about other names: a model
that takes the one name `UTF-8` may leave them at the JDK call, and must never prove `ascii`, `latin`, `unknown` or
`chosen`. `defaulted` is the challenge stream's I008 as a pair: a check that proves it has assumed the default
charset.

What each row guards against:

- `named`: the model exists and is the other overload's bytes; the handler's `AssertionError` is not reachable.
- `written`, `lone`, `paired`: the named overload replaces a lone surrogate with `?` and writes a pair as four
  bytes. Its Javadoc leaves malformed input unspecified (VF-038); the bytes are the implementation's, which
  `examples/307-*/records/conversion/` records for the pinned JDKs.
- `asciiWritten`, `asciiPairs`: `String.encodeASCII` writes one `?` for a surrogate pair, not two. A model that
  maps each unit from 0x80 to `?` is wrong on every supplementary character, and its array is one byte too long.
- `ascii`, `latin`, `unknown`, `chosen`: the model must read the name. One keyed on the descriptor
  `getBytes(String)` alone proves all four.
- `alias`: `UTF8` is UTF-8 on a JVM (`Charset.forName` gives the same object), so it is no wrong conversion. A
  check must not refute it.

## What was run

`check.py` compiles both versions, runs each `main` on a JVM (as it is, and under COMPAT with `LC_ALL=C`), refuses
to go on if the JVM contradicts the table, and checks each pair:

```
jvmcontract equivalence --before old --after new --target app.Text#NAME --nullable s \
  --assume 'k >= -1 && k <= 12' --engine native --max-array-length 3 --jbmc /nonexistent/jbmc
```

Three checkers, each built apart from the preservation stream's `rmvpqswzxlyv` (git `e461ac1d2c5f`, its last
commit before the I010 fix), on JDK 25.0.5, about 7 s for the twelve:

| Checker | `named` `written` `asciiWritten` | `lone` `paired` `asciiPairs` | `ascii` `latin` `unknown` `chosen` | `alias` | `defaulted` |
|---|---|---|---|---|---|
| as committed | no verdict: each stops at `getBytes` or at `US_ASCII` | no verdict, the same stops | no verdict | no verdict | no verdict |
| with `prototype-model.patch` | **verified** | **violation**, each replayed | no verdict (the name is not `UTF-8`) | no verdict | no verdict |
| the prototype made wrong on purpose (any name is UTF-8; each surrogate of a pair is its own `?`) | `named` and `written` verified, `asciiWritten` **not** (its witness does not replay) | `lone` and `paired` violations, `asciiPairs` **verified** | **all four verified** | verified | no verdict |

So the fixtures tell a right model from two wrong ones: the wrong prototype is caught on six pairs, five of them
false proofs. `check.py --model-landed` exits 1 on each.

## The prototype

`prototype-model.patch` is against `lib/src/bmc/bytes.rs` and `lib/src/bmc/mod.rs` at `rmvpqswzxlyv`. It is a
sketch to show the size of the change (about 80 lines) and to run the fixtures against something, not a proposal
to merge as it is: it has no row in `values.rs`'s table of modelled calls, no entry in `lib/README.md`, and the
static gap scan (`bmc/gaps.rs`) will now say `getBytes(String)` is modelled for every name, where the engine takes
one. What it does:

- `String.getBytes(String)`: `NullPointerException` for a null name, as `lookupCharset`'s `requireNonNull` throws
  before the String is read. For a name whose units are the constant `UTF-8`, the bytes `utf8()` already
  computes for the other overload. Any other name, or one whose units the engine does not know, stays the JDK call.
  The two overloads then give one circuit for one String, which is what lets a tie or a shared callee see equal
  arguments on both sides without a solver call.
- `StandardCharsets.US_ASCII` is one object for the run, as `UTF_8` is, and `getBytes` with it is `ascii()`: a unit
  below 0x80 is itself, any other is `?`, and the low surrogate of a pair writes nothing.

Why the named overload may be modelled as the other one, on the pinned JDKs: in OpenJDK 21 and 25
`getBytes(String)` is `encode(lookupCharset(name), coder(), value)` and `getBytes(Charset)` is `encode(charset,
coder(), value)` after a null check (the bytecode is in `examples/307-*/records/conversion/jdk-*.json`, under
`runtime.stringBytecode`). `lookupCharset("UTF-8")` is `Charset.forName`, which gives the object
`StandardCharsets.UTF_8` is (recorded there as `names[0].forName`); the standard provider is asked first, so no
`CharsetProvider` on the class path can answer for that name. UTF-8 is a charset every Java platform has, so the
lookup does not throw. This is a fact about those builds, not about the Javadoc: see VF-038.

## The test to add with the model

For `lib/tests/` (a tool-tier test: javac and the checker, a few seconds), with the fixtures compiled as
`tie_countermodels.rs` compiles its own:

```rust
/// A model of `String.getBytes("UTF-8")` and of the US-ASCII conversion proves the pairs a JVM cannot tell apart,
/// refutes the ones it can, and proves no pair that names another charset.
#[test]
fn the_named_conversion_is_utf8_for_that_name_alone_and_ascii_writes_one_byte_for_a_pair() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let check = |name: &str| {
        let mut o = equivalence::Options::new(old, new, &format!("app.Text#{name}"));
        o.jbmc = "/nonexistent/jbmc".into();
        o.engine = Engine::Native;
        o.nullable = vec!["s".into()];
        o.assume = Some("k >= -1 && k <= 12".into());
        o.max_array_length = 3;
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("conversion-countermodels").join(name));
        equivalence::run(&o).unwrap().verdict
    };
    for name in ["named", "written", "asciiWritten"] {
        assert_eq!(check(name), Verdict::Verified, "{name}");
    }
    for name in ["lone", "paired", "asciiPairs"] {
        assert_eq!(check(name), Verdict::Violation, "{name}");
    }
    for name in ["ascii", "latin", "unknown", "chosen", "defaulted"] {
        assert_ne!(check(name), Verdict::Verified, "{name}");
    }
    assert_ne!(check("alias"), Verdict::Violation);
}
```

The fields are `equivalence::Options`'s at `rmvpqswzxlyv` (`assume`, `nullable`, `max_array_length`, `engine`,
`jbmc`, `work`); the test itself was not compiled, since it can pass only with the model.
