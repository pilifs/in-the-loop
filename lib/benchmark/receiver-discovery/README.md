# Receiver construction and physical observations

`jvmcontract construct TYPE --classes DIR --observer CLASS#METHOD --output DIR` enumerates compatible public constructors and static factories on the supplied classpath. Each generated static entry accepts the producer's primitive arguments, calls the original producer once and passes the returned object to the observer. The observer can also receive a matching prefix of the producer's arguments. Its public calls define the subsequent history. The JSON names every included producer and each omitted candidate. A proof applies to one such history.

`jvmcontract sites CLASS#METHOD --classes DIR` lists candidate checks in the bound original method. Each row identifies the byte offset, opcode, exception handlers and check kind. Inspect the inventory again after recompilation.

To investigate the caught divide in example 398, compile its original sources with Temurin 21.0.13, then run the following from the repository root.

```bash
R=lib/benchmark/receiver-discovery
C="$TMPDIR/safety-original"
mkdir -p "$C"
"$JAVA21_HOME/bin/javac" -proc:none -parameters -g -d "$C" examples/398-physical-safety-sites/original/*.java
python3 -B "$R/investigate.py" --checker lib/target/release/jvmcontract \
  --classes "$C" --entry 'SafetyClaims#dividing' --target 'SafetySites#run' \
  --sha256 880b0dd04dcdc83437618fd303dabff245f59971bab4b1edf86c0374a681ead2 \
  --pc 19 --kind division-by-zero --policy occurrence --unwind 9 --max-array-length 8 \
  --output "$TMPDIR/caught-divide"
```

The selected proof runs on a private projection of the bound class. It adds observer-owned state around one instruction. Its first synthetic handler remembers the actual exception and rethrows it inside the original protected region. The last handler checks whether that same object left the selected method activation. Branch policies record the original branch edge. A separate query checks the original backward-edge budget per activation. Reachability, the no-event claim and completeness each retain their strict native result. An original JVM replay uses a breakpoint at the requested byte offset and records actual exception and catch locations, branch successors or the selected return value. The projection assumes a single-threaded history, available VM resources and an isolated observer namespace. [JDK exception-event semantics](https://docs.oracle.com/en/java/javase/21/docs/api/jdk.jdi/com/sun/jdi/event/ExceptionEvent.html)

Run `python3 -B lib/benchmark/receiver-discovery/qualification.py stock --checker lib/target/release/jvmcontract --output "$TMPDIR/stock-history"` for a physical branch on a discovered stock receiver and its independent alias-sensitive histories. The `--null-collaborators` construction policy supplies null for reference inputs and retains arbitrary primitive inputs. With `--fresh-observer-inputs`, primitive arguments after the observer's receiver are independent of the producer arguments.
