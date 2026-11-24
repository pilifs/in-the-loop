# Receiver construction and physical observations

Build the checkout’s executable with `cargo build --offline --release --manifest-path lib/Cargo.toml --bin jvmcontract`. The managed experiment uses the pinned artifacts and JDK recorded in the campaign brief. The examples below use a cache directory for temporary files.

`jvmcontract construct TYPE --classes DIR --observer CLASS#METHOD --output DIR` enumerates compatible public constructors and static factories on the supplied classpath. Each generated static entry accepts the producer's primitive arguments, calls the original producer once and passes the returned object to the observer. The observer can also receive a matching prefix of the producer's arguments. Its public calls define the subsequent history. The JSON names every included producer and each omitted candidate. A proof applies to one such history.

`jvmcontract sites CLASS#METHOD --classes DIR` lists candidate checks in the bound original method. Each row identifies the byte offset, opcode, exception handlers and check kind. Inspect the inventory again after recompilation.

To investigate the caught divide in example 398, compile its original sources with Temurin 21.0.13, then run the following from the repository root.

```bash
export TMPDIR="${TMPDIR:-$HOME/.cache/in-the-loop/tmp}"
mkdir -p "$TMPDIR"
JAVA21_HOME="$HOME/.sdkman/candidates/java/21.0.13.0+9-tem"
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

`jvmcontract prove TARGET --engine native --gaps strict --search-startup-witness` can seek a violating primitive input after an ordinary property proof stops on a literal `System.getProperty` read in a class initializer. The search tries a one-character nonempty value in a disposable harness. A fresh JVM runs the original harness with its normal startup and classpath on the solver’s proposed input. The command reports a violation only if that original harness fails and the original public call returns an observable value. Otherwise it keeps the original refusal. The search currently handles a public static entry with primitive inputs, a primitive return and one unresolved literal property key. Its witness is reproducible on the unchanged public entry. [JavaParser and XZ measurements](../../../verification/receiver-discovery/transfer)

The separately recorded fresh-process experiments call `System.setProperty` or `System.clearProperty` before invoking the original public method. Their receipts keep both the selected process prestate and the fresh-default result for the same input. A successful restricted run supplies a conditional proof. A false return at the unchanged entry supplies a concrete counterexample for an ordinary scope that admits that prestate. [Fresh-process checks](process_states.py) · [Public witness qualification](property_witness.py)

To select the branch reached by an automatically constructed stock, use the generated entry printed by the checker.

```bash
export TMPDIR="${TMPDIR:-$HOME/.cache/in-the-loop/tmp}"
mkdir -p "$TMPDIR"
R=lib/benchmark/receiver-discovery
J="$HOME/.sdkman/candidates/java/21.0.13.0+9-tem"
B=lib/target/release/jvmcontract
S=$(mktemp -d "$TMPDIR/stock-site.XXXXXXXX")
mkdir "$S/original"
"$J/bin/javac" -g -parameters -proc:none -d "$S/original" examples/397-*/original/*.java
JAVA_HOME="$J" JVMCONTRACT_JAR_RELEASE=21 "$B" construct 'Checkout$Pair' \
  --observer 'InventoryChecks#taken' --classes "$S/original" --output "$S/generated" > "$S/history.json"
ENTRY=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["plans"][0]["entry"])' "$S/history.json")
python3 -B "$R/investigate.py" --checker "$B" --classes "$S/generated" --classes "$S/original" \
  --entry "$ENTRY" --target 'Checkout$Stock#take' \
  --sha256 2ad22dd17898c3f447ddb71e9b4ba8a3043d2e61337f70349d346f1e5281dd82 \
  --pc 4 --kind branch --policy taken --unwind 9 --max-array-length 8 --output "$S/selected"
```

The resulting receipt contains a witness that the selected edge can be taken. The original JVM replay gives its next instruction offset. The separate unchanged-backup claim replays the shared, positive stock through the same public producer.
