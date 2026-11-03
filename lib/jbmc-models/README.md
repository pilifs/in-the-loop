# `lib/jbmc-models/`: JDK classes JBMC needs a model of

JBMC 6.11 embeds no model of the Java Class Library (the CProver [models library](../../libs/README.md) is a jar one puts on the classpath). `jvmcontract` gives JBMC six real JDK classes it extracts from the running JDK's image (`Byte`, `Short`, `Integer`, `Long`, `Math`, `StrictMath`); every other JDK class is a stub whose methods return nondeterministic values and whose static fields are nondeterministic references, which under `--throw-runtime-exceptions` become `NullPointerException`s and `ArrayIndexOutOfBoundsException`s on paths the real JDK never takes. Two kinds of class need more than a stub, and this directory holds Java sources for them:

| Source | Models | Why |
|---|---|---|
| `java/lang/Integer$IntegerCache.java`, `Long$LongCache`, `Short$ShortCache`, `Byte$ByteCache` | The nested cache classes the real `valueOf` methods read | The JDK's `Integer.valueOf(int)` is `if (i >= IntegerCache.low && i <= IntegerCache.high) return IntegerCache.cache[i + 128]`. JBMC has `Integer` but not `Integer$IntegerCache`, so `high` and `cache` are nondeterministic and `valueOf` throws `ArrayIndexOutOfBoundsException` on inputs the real cache covers, which turns any autoboxing (a varargs call, say) into a false violation. The models declare an empty range, so `valueOf` allocates every time, as the CProver models library's own `Integer.valueOf` does; identity of boxed small values is the one observable difference. Fields are assigned in a static block because JBMC does not read `ConstantValue` attributes. |

`java.nio.charset.Charset` and `StandardCharsets` are modelled in the [forked models library](../../libs/README.md) instead, since they are models of public API that belong upstream.

Until `jvmcontract` ships these itself, compile them and pass the directory on the classpath of `equivalence` and `prove`:

```bash
javac --release 8 -d /tmp/jbmc-models lib/jbmc-models/java/lang/*.java libs/java-models-library/src/main/java/java/nio/charset/*.java
jvmcontract prove 'org.apache.commons.codec.binary.Hex#toDigit' --classes head/classes --classpath /tmp/jbmc-models ...
```

The classpath is shared with the interpreter that replays witnesses, which runs a class file it finds there in preference to its own natives; these models and the charset models execute fine in it. Do not put real JDK classes (`java.lang.Character` and its `CharacterData` tables, say) on it: the interpreter would run their static initializers and stop at the first native they need, and JBMC's reading of the tables is not reliable either ([commons-codec 43a9aa66](../../examples/109-commons-codec-43a9aa66-hex-decoding-restricted-to-ascii/README.md) has the measurements).
