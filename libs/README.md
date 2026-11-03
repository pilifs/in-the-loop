# `libs/`: forked libraries the verifier builds on

Plain clones, not tracked by this repository (see [`.gitignore`](../.gitignore)); each entry says where the fork is and what it changes. A build strategy that ties them in comes later.

| Folder | Fork of | Branch | What it changes |
|---|---|---|---|
| `java-models-library/` | [diffblue/java-models-library](https://github.com/diffblue/java-models-library), the Java Class Library models for JBMC, built as `core-models.jar` | [`pilifs/java-models-library`](https://github.com/pilifs/java-models-library/tree/charset-models), branch `charset-models` | Adds `java.nio.charset.Charset`, `StandardCharsets`, `IllegalCharsetNameException` and `UnsupportedCharsetException`. Without them JBMC has no class for `StandardCharsets`, a read of `StandardCharsets.UTF_8` is a stub reference, and under `--throw-runtime-exceptions` any static initializer that uses it (Apache Commons Codec's `CharEncoding`, say) ends in a `NullPointerException`, which turns every proof over such a class into a false violation. Found on [commons-codec commit 43a9aa66](../examples/109-commons-codec-43a9aa66-hex-decoding-restricted-to-ascii/README.md). |

To get the clone:

```bash
git clone -b charset-models git@github.com:pilifs/java-models-library.git libs/java-models-library
```

JBMC 6.11 embeds no models: the library's `core-models.jar` is meant to go on the classpath, and `jvmcontract` gives JBMC only six real JDK classes. So the models are used by compiling them and passing the directory on `jvmcontract`'s `--classpath` for `equivalence` and `prove`: `javac --release 8 -d <dir> libs/java-models-library/src/main/java/java/nio/charset/*.java`, together with the cache models in [`lib/jbmc-models/`](../lib/jbmc-models/README.md). JBMC loads a class from the first classpath entry that has it, and the interpreter that replays witnesses runs the same class files. The library's own Maven build needs JDK 8 (it compiles against `rt.jar`), and its current sources do not compile as a whole on a newer JDK; the four classes compile on their own with any JDK.
