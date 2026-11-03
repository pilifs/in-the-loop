# Bytecode verification of apache/commons-codec commit 43a9aa66: `Hex` decoding restricted to ASCII hexadecimal characters

[← All examples](../README.md)

Not a pull request: [a maintainer's commit](https://github.com/apache/commons-codec/commit/43a9aa663c1b10b32a7cc6bbc1eccc10bba5f9be) to `master` on 2026-09-18, compared with its parent `87f6aa28`. It changes `Hex.toDigit(char, int)`, the method every `decodeHex` overload calls per character, from `Character.digit(ch, 16)` to three explicit ASCII ranges, so that Unicode digits such as the Arabic-Indic zero `U+0660` or the fullwidth `０` are rejected instead of decoded; the Javadoc explains that such spellings could bypass textual blocklists that compare hexadecimal strings without decoding them. The exception message changes from `ch & 0xFF` to `ch & 0xFFFF`. Sixteen lines of tests.

This is the record of a commit that the verifier could not handle as the skill runs today, and of what it took to get a verdict. `Hex`'s static initializer reads `StandardCharsets.UTF_8`, a class JBMC has no bytecode for; the tool's first answer was a violation that was an artifact of that, and so was its second, from `Integer.valueOf` boxing the exception message's arguments. With a model of `java.nio.charset` written for the occasion ([a fork of the CProver models library](../../libs/README.md)) and a model of the JDK's boxing caches ([`lib/jbmc-models/`](../../lib/jbmc-models/README.md)), the new `toDigit` is proved in full: the digit value for the twenty-two ASCII characters and `DecoderException` for every other `char`. The old `toDigit` stays out of reach, because `Character.digit` is not modelled either by JBMC or by the interpreter, and the regression proof needs both versions. The module's capability and API contracts are unchanged.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `Hex#toDigit(char, int)`, new version | property: `result` is the digit's value for `0-9`, `A-F`, `a-f`, under the assumption `ch` is one of them | ✓ Verified | with the charset models on the classpath; 0.5 s |
| `Hex#toDigit(char, int)`, new version | property: `0 <= result <= 15`, and `DecoderException` whenever `ch` is not one of the twenty-two | ✓ Verified | with the charset and cache models; 0.8 s. Every `char` × every `int` index |
| `Hex#toDigit(char, int)` | regression (equivalence) | ⚠ Unverifiable | the old version calls `Character.digit`, which JBMC has no bytecode for: without it the witnesses are artifacts (`toDigit(':', 0)`, on which both versions throw); with the JDK's own `Character` and `CharacterData` classes given to JBMC, it answers that `toDigit('٠', 0)` is not `0` on the old version, where the JVM returns `0`. Neither reading can be trusted, and the interpreter cannot replay either |
| `Hex#decodeHex(char[])`, `decodeHex(char[], byte[], int)` | regression (equivalence) | ⚠ Unverifiable | call `toDigit`; at the default bounds JBMC ran out of memory in 74 s before the models were in place, and the proof needs the old `toDigit` |
| the exception message, `ch & 0xFF` to `ch & 0xFFFF` | none | not covered | the proofs compare exception types, not messages; the interpreter also declines to compute this one, because `%,d` depends on the default locale |
| `encodeHex` and the rest of `Hex` | none | unchanged by the commit |

## Findings

### What the tool said first, and why it was wrong

```
✗ Behaviour of org.apache.commons.codec.binary.Hex#toDigit changed:
  toDigit(ch='\u001e', index=5)
    before: <could not replay: <unsupported: reads static field java.nio.charset.StandardCharsets.UTF_8>>
    after:  <could not replay: <unsupported: reads static field java.nio.charset.StandardCharsets.UTF_8>>
  (found by JBMC 6.11.0 in 0.4 s searching inputs in [0:20], replayed in the interpreter; domain ch: char × index: int)
```

Both versions throw `DecoderException` on `U+001E`. JBMC's trace shows what it found instead: `Hex.<clinit>` reads `StandardCharsets.UTF_8` and `CharEncoding.UTF_8`, and `CharEncoding.<clinit>` calls `StandardCharsets.ISO_8859_1.name()`. JBMC 6.11 embeds no model of the class library, and `jvmcontract` gives it six JDK classes (`Byte`, `Short`, `Integer`, `Long`, `Math`, `StrictMath`); `StandardCharsets` is a stub whose static fields are nondeterministic references, and under `--throw-runtime-exceptions` the call on one of them is a `NullPointerException` in class initialization, before `toDigit` runs. The harness saw an exception it did not expect and reported a difference. The interpreter, which replays every witness to confirm it, refused for the same reason, so the artifact went through as a violation. Every proof over `Hex` failed this way, including a property of the new version alone.

The same run surfaced a smaller gap: the expression language has no character literals, although the skill's reference says it does, so `ch >= '0'` had to be written `ch >= 48`.

### The charset models, and the second artifact

With `java.nio.charset.Charset` and `StandardCharsets` modelled (the six standard charsets as named instances; [the fork](https://github.com/pilifs/java-models-library/tree/charset-models)) and the classes on `jvmcontract`'s `--classpath`, `Hex` initializes and the ASCII property proves in 0.5 s. The property with the throws clause still reported a violation at `toDigit('\u0000', 0)`, and the trace showed why: `DecoderException(String format, Object... args)` boxes `ch & 0xFFFF` with `Integer.valueOf`, the JDK's `Integer.valueOf` reads `Integer$IntegerCache.high` and `.cache`, and that nested class is not among the six, so the cache was a nondeterministic array and the read an `ArrayIndexOutOfBoundsException`. A model of the four cache classes with an empty range, so that `valueOf` allocates (as the CProver library's own `Integer` does), removed it; a first version with a filled 256-element cache exceeded the unwinding bound, and a second with `ConstantValue` fields failed because JBMC does not read them. With both model sets the exception-path property proves in 0.8 s:

```
✓ org.apache.commons.codec.binary.Hex#toDigit satisfies `result >= 0 && result <= 15` on every input, and throws org.apache.commons.codec.DecoderException when !((ch >= 48 && ch <= 57) || (ch >= 65 && ch <= 70) || (ch >= 97 && ch <= 102)) (JBMC 6.11.0: 2 properties proved over ch: char × index: int in 0.8 s; loops unwound 16 times with unwinding assertions)
```

Together with the first property this is the whole contract of the new method: on every one of the 65,536 characters and every index, the ASCII hexadecimal digits decode to their value and nothing else decodes.

### The old version, and `Character.digit`

The regression proof needs the old `toDigit`, which is `Character.digit(ch, 16)`. JBMC has no bytecode for `Character`, so the method is a stub returning any `int`, and the proof's witnesses are inputs on which both versions throw. Giving JBMC the JDK's own `Character`, `CharacterData` and `CharacterDataLatin1`..`CharacterData0E` classes, extracted from the JDK image, did not help: a property stating that `toDigit('٠', 0)` is `0` on the old version, which is what the JVM computes (`Character.digit('٠', 16) == 0`), came back as violated in 6.2 s, so JBMC's reading of the tables (static arrays built from string literals in `<clinit>`) is wrong somewhere, and a verdict built on it would be too. The interpreter cannot replay these witnesses either: with the real `Character` class on its classpath it runs the class's static initializer and stops at `Class.getPrimitiveClass`, and without it it has no `Character.digit` of its own. What the commit changes for non-ASCII digits is therefore stated by its tests and its Javadoc, not proved here; proving it needs a model of `Character.digit`, which is a table of the Unicode decimal-digit ranges, in the models library.

## Not covered

- The regression proof and the `decodeHex` overloads, as above.
- The exception message. Note that the interpreter's refusal, `String.format depends on the default locale`, is correct: `%,d` inserts the locale's grouping separator, so the message text is not a function of the inputs alone.

## Module-level contracts

**Capabilities**: unchanged, 135 classes and 1,333 methods before and after. **Public API**: unchanged (1,171 lines).

## How this was produced

- The commit and its parent were checked out from a `--filter=blob:none` clone of `apache/commons-codec` into two worktrees on 2026-11-02; the skill's `fetch-pr.sh` takes a pull request, and this is a commit, so the two `git worktree add` commands stood in for it.
- The module has no compile-time dependencies, so both versions were compiled with `javac -proc:none -parameters -g` over `src/main/java` (135 classes each); Maven was not run.
- Models: `java/nio/charset/{Charset,StandardCharsets,IllegalCharsetNameException,UnsupportedCharsetException}.java` from the fork's `charset-models` branch, and `java/lang/{Integer$IntegerCache,Long$LongCache,Short$ShortCache,Byte$ByteCache}.java` from `lib/jbmc-models/`, compiled with `javac --release 8` into one directory, `$MODELS`. For the `Character` experiment, `jimage extract` of `java/lang/Character*.class` and `java/lang/CharacterData*.class` from the JDK's `lib/modules` into `$CHARS`.
- Tools: `jvmcontract` from this repository, JBMC 6.11.0, JDK 25.
- The commands behind the verdicts in the table:

```bash
T='org.apache.commons.codec.binary.Hex#toDigit'
HEX='((ch >= 48 && ch <= 57) || (ch >= 65 && ch <= 70) || (ch >= 97 && ch <= 102))'
jvmcontract equivalence --before base-classes --after head-classes --target "$T" --timeout 600          # the first artifact, no models
jvmcontract prove "$T" --classes head-classes --classpath "$MODELS" --assume "$HEX" \
    --assert 'result >= 0 && result <= 15 && (ch < 48 || ch > 57 || result == ch - 48) && (ch < 65 || ch > 70 || result == ch - 65 + 10) && (ch < 97 || ch > 102 || result == ch - 97 + 10)' --timeout 300
jvmcontract prove "$T" --classes head-classes --classpath "$MODELS" --throws "org.apache.commons.codec.DecoderException when !$HEX" --assert 'result >= 0 && result <= 15' --timeout 300
jvmcontract prove "$T" --classes base-classes --classpath "$MODELS:$CHARS/java.base" --assume 'ch == 0x0660' --assert 'result == 0' --timeout 300   # the wrong answer
jvmcontract equivalence --before base-classes --after head-classes --target "$T" --classpath "$MODELS:$CHARS/java.base" --timeout 300
jvmcontract capabilities base-classes --module commons-codec > capabilities-base.txt
jvmcontract capabilities head-classes --module commons-codec > capabilities-head.txt
jvmcontract api base-classes --module commons-codec > api-base.txt
jvmcontract api head-classes --module commons-codec > api-head.txt
```

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass.
