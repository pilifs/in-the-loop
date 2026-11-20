# Apache Commons Text PR #586

Upgrade Apache Commons Text · Commons Lang 3.16.0 → 3.17.0  
Caller-visible behavior `StringEscapeUtils.escapeCsv` returns the characters of one CSV field. Dropping quote doubling changes what a CSV reader receives.  
Result Both revisions returned the exact expected characters on 156/156 fields. The V0 workflow stopped while decoding modified UTF-8 in the original `StringEscapeUtils.class`. [JVM observations](records/full-source-jvm.json) · [Workflow failure](records/workflow-intake.json)  
Scope Every non-null string of length 0–3 over `a`, comma, double quote, CR and LF, on Temurin 21.0.13+9.  
Review action Accept the upgrade for this CSV behavior. Keep the existing quote-doubling tests. Longer fields and other characters require separate evidence.

The two PR archives contain 242 files each. Only the Commons Lang version in `pom.xml` changes. Both effective POMs give Commons Text one production dependency. Compiling all 107 original Java sources independently produced the same 153 classes and the same complete client JAR on both sides. Class-loading logs identified the byte-identical caller and each side’s actual Lang `StringUtils`. [Pull request](https://github.com/apache/commons-text/pull/586) · [Source and artifact lock](sources.lock.json) · [Effective POMs and classpath closure](records/build-and-ci.json)

The Python oracle independently enumerates 1 + 5 + 25 + 125 fields. It encloses fields containing a special character and doubles embedded quotes. The JVM driver reports UTF-16 units and exceptions. A constructed change in the original translator removed quote doubling and caused 71 disagreements. A single U+0022 returned four quote characters on both original builds and three on the mutant. [Original returns](records/observations-upgrade.jsonl) · [Mutant returns](records/observations-mutant.jsonl) · [Mutant patch](controls/omit-quote-doubling.patch)

The historical `StringEscapeUtilsTest` class passed all 34 methods on each revision. Two of those tests caught the mutant. The exhaustive observer adds coverage of every combination in the stated domain. Both offline attempts at the full Maven CI command stopped before testing because the Apache RAT plugin was unavailable. The GitHub API returned no retained workflow or check runs for the head SHA. [Old JUnit testcases](records/junit-old.xml) · [New JUnit testcases](records/junit-new.xml) · [Mutant JUnit testcases](records/junit-mutant.xml) · [CI evidence](records/build-and-ci.json)

The standard workflow tried to decode the legal constant-pool encoding `C0 80` for U+0000 with Python’s ordinary UTF-8 decoder. The first replay process exited 1 while inspecting the original class. Its attempt file still shows the last completed stage, `planned`. A separate assisted invocation passed the hash-checked full class directories to the public native CLI. Strict mode refused the old `StringEscapeUtils.<clinit>()` at `RegressionPair.agree:41`. This run used the V0 binary and bundled CaDiCaL. The campaign configuration selects Bitwuzla. [Intake traceback](records/workflow-intake.log) · [Direct CLI result](records/native-cli-outcome.json) · [Probe identity and timing](records/native-cli-run.json)

## Reproduction

In this directory, put the five files named in `sources.lock.json` under `$INPUTS`. The script verifies each SHA-256 before compilation and requires a new work directory. It prints the three observation and JUnit totals. Its output directory retains full JARs, observed values, load logs and original JUnit XML.

```sh
python3 -I reproduce.py --inputs "$INPUTS" --jdk "$JDK21_HOME" --work "$WORK"
```

To reconstruct the full effective POMs, put the three POMs under their Maven repository paths in `$MODEL_REPO`. Their URLs and hashes are in the CI record. Use the same Maven 3.10.0 distribution and JDK 21 and pass either original source POM to Maven’s model builder. The saved gzip files replace the checkout and home directories with portable placeholders. [Old effective model](records/effective-old.xml.gz) · [New effective model](records/effective-new.xml.gz)

```sh
"$JDK21_HOME/bin/java" -cp "$MAVEN_HOME/lib/*" reproduction/EffectivePom.java \
    "$SOURCE/pom.xml" "$MODEL_REPO" "$OUTPUT_XML"
```

The campaign disclosed the client, entry, expected rule and mutant before this calibration. This result contributes zero cases to the 24 scored upgrades and eight transfer upgrades. [Independent adjudication](records/adjudication.json)
