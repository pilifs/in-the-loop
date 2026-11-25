# Four disputed predictions on current Java code

On 2026-11-25 the four registered callers ran against published Maven artifacts and the then-current default Git branches. The same compiled historical caller ran on both deployments of each artifact. The trials checked the class loader's source for the implementation under test. Three histories expose upstream defects. The Jackson history exposes an incorrect prediction about a specific iterator configuration. [Frozen inputs and SHA-256 digests](inputs.json) · [Historical comparisons](../../../llm-dlc/loops/organic-java-merged-pr-links-brief-results.md)

## Reproduction

From this checkout, select an example number. The command builds the relevant Java sources from the recorded Git commit, runs its caller on the release and the development build, and compares the full observations with the saved receipt. It uses the campaign's Temurin 21.0.13+9. Set `PUBLIC_COMPARISON_JDK` to that installation if it is outside SDKMAN. The first run can fetch missing public inputs. Subsequent runs can use the same cache offline.

```sh
python3 verification/merged-pr-links/upstream/recheck.py 411 --fetch
python3 verification/merged-pr-links/upstream/recheck.py 411
```

To run a caller in an upstream checkout, use JDK 21, put the linked `PublicCaller.java` beside this `Reproduce.java`, and set `CP` to that project's runtime classpath. Each report gives its argument.

```java
public class Reproduce {
    public static void main(String[] args) throws Exception {
        System.out.println(PublicCaller.observe(args));
    }
}
```

```sh
javac -cp "$CP" PublicCaller.java Reproduce.java
java -cp ".:$CP" Reproduce array-orders
```

The three reports below are ready for the user to file or attach to a related issue. The upstream tracker checks described here were made on 2026-11-25.

## Apache Avro · Scalar-first union throws when reading or emitting an array default

**Affected versions.** Avro and avro-idl 1.12.2 from Maven Central and `main` at `a3355d0826fa`. [Public caller](../../../examples/411-avro-idl-union-default/caller/PublicCaller.java) · [Release and development observations](411.json)

**Reproduce.** Run `array-orders`. Parse the following record using `new Schema.Parser().parse(json)`. Read `schema.getField("f").defaultVal()` and call `IdlUtils.writeIdlSchema(writer, schema)` independently. Repeat with the two union branches exchanged.

```json
{"type":"record","name":"R","namespace":"example","fields":[
  {"name":"f","type":["int",{"type":"array","items":"int"}],"default":[1]}
]}
```

**Expected and observed.** Only the array branch matches the default, in either position. With the array first, the getter returns a list containing `Integer(1)` and the IDL initializer is `[1]`. With the integer first, the parser accepts the record and `hasDefaultValue()` is true, but the getter and writer each throw `AvroRuntimeException`. The control `["int","null"]` with default `1` returns the integer and emits the literal. The conversion code asks the current candidate schema for its element type while visiting a nonempty JSON array. [Union default specification](https://avro.apache.org/docs/1.12.0/specification/#records) · [Conversion at the tested commit](https://github.com/apache/avro/blob/a3355d0826faf583fb704b16d8bf9df3d501a689/lang/java/avro/src/main/java/org/apache/avro/util/internal/JacksonUtils.java#L116-L179)

**Related reports.** AVRO-4211 covers this conversion path and was resolved for the scalar case. AVRO-4238 concerns schema evolution through the fast reader, and AVRO-4273 concerns a null default in `GenericData`. The array-order reproduction can be attached to AVRO-4211 or filed as a linked follow-up. [AVRO-4211](https://issues.apache.org/jira/browse/AVRO-4211) · [AVRO-4238](https://issues.apache.org/jira/browse/AVRO-4238) · [AVRO-4273](https://issues.apache.org/jira/browse/AVRO-4273)

## ical4j · Reordering two distinct recurrence overrides drops a meeting

**Affected version.** The merge of #931 and `develop` at `2c5ff9f211a8` both depend on input order. The published 4.4.0 release predates #931 and returns the original two master periods in both orders. [Public caller and complete calendar](../../../examples/412-ical4j-moved-occurrences/caller/PublicCaller.java) · [Release and development observations](412.json)

**Reproduce.** Run `two-orders`. Start with a daily UTC event at midnight lasting 30 minutes. Give two overrides the same series UID and the following UTC values. Query `ComponentGroup.calculateRecurrenceSet` from July 14 at noon to July 16 at noon. Exchange only the two override components in the calendar and repeat. All dates are in July 2021.

| Override | Original occurrence (`RECURRENCE-ID`) | Replacement start | Duration |
|---|---|---|---|
| A | July 15 00:00 | July 16 00:00 | 90 minutes |
| B | July 16 00:00 | July 16 03:00 | 60 minutes |

**Expected and observed.** Each override identifies a different original occurrence, and both replacements are inside the window. Input order B,A returns both replacement periods with their correct durations and owners. A,B returns only B. The implementation removes matches by start time from a list that already contains A's replacement, whose start equals B's recurrence ID. The control without overrides follows the current end-exclusive period contract. The challenge's noon boundaries put both replacements strictly inside the window. [Recurrence-ID semantics](https://www.rfc-editor.org/rfc/rfc5545#section-3.8.4.4) · [Component group contract](https://github.com/ical4j/ical4j/blob/2c5ff9f211a880d86439bfe34b72dc0b0a28872e/openspec/specs/component-group-recurrence-set/spec.md) · [Replacement loop](https://github.com/ical4j/ical4j/blob/2c5ff9f211a880d86439bfe34b72dc0b0a28872e/src/main/java/net/fortuna/ical4j/model/ComponentGroup.java#L157-L176)

**Related reports.** #509 and #510 describe single overrides. #931 implemented rescheduling. #936 later made the end of the query period exclusive. The tracker search found no report for exchanging two overrides at colliding starts. [Issue #509](https://github.com/ical4j/ical4j/issues/509) · [Issue #510](https://github.com/ical4j/ical4j/issues/510) · [PR #931](https://github.com/ical4j/ical4j/pull/931) · [PR #936](https://github.com/ical4j/ical4j/pull/936)

## jOOλ · Widening an already complete window changes its last value

**Affected versions.** Both `org.jooq:jool` and `org.jooq:jool-java-8` at release 0.9.16 and on `main` at `9273e1f54356`. Both artifacts ran on the registered Java 21 VM. [Public caller](../../../examples/419-jool-window-endpoints/caller/PublicCaller.java) · [Results for both modules](419.json)

**Reproduce.** Run `overflow`. On `Seq.of(1, 2, 3).window(-5, upper)`, collect `firstValue()` and `lastValue()` for the third input row. Set `upper` to `5`, then `Long.MAX_VALUE - 1`. The ordinary frame covers every row, so widening it should leave the endpoints at 1 and 3. Every tested deployment returned (1,3) for 5 and (1,1) for the wider frame. The future-only frame control passed in both modules. The implementation adds the row index to the finite bound before clamping it. For index 2 the sum wraps to `Long.MIN_VALUE`, which narrows to index zero. [Window endpoint contract](https://github.com/jOOQ/jOOL/blob/9273e1f54356278337981370a51a9763c4fd1dc4/jOOL/src/main/java/org/jooq/lambda/Window.java#L61-L68) · [Bound calculation](https://github.com/jOOQ/jOOL/blob/9273e1f54356278337981370a51a9763c4fd1dc4/jOOL/src/main/java/org/jooq/lambda/WindowImpl.java#L96-L104)

**Related reports.** #417 and #418 cover ordinary out-of-partition endpoints. The implementation contains an overflow TODO. The tracker search found no separate report of this finite-bound example. [Issue #417](https://github.com/jOOQ/jOOL/issues/417) · [PR #418](https://github.com/jOOQ/jOOL/pull/418)

## Jackson CSV · Correction to the brief's row-iteration prediction

The brief asked a schema-less `MappingIterator<String[]>` to consume multiple row arrays with `WRAP_AS_ARRAY` disabled. Jackson's documented recipe and its multirow regression enable this feature. The unwrapped input exposes each row as a top-level array, and the databinding iterator can interpret the first array as the sequence it should consume. The merged regression separately promises normal exhaustion for its single-row input. [CSV guide](https://github.com/FasterXML/jackson-dataformats-text/blob/eb84c31b9dbaa4eaa5ae704a0ad4710862b17ea1/csv/README.md#data-binding-without-schema) · [Multirow iterator test](https://github.com/FasterXML/jackson-dataformats-text/blob/eb84c31b9dbaa4eaa5ae704a0ad4710862b17ea1/csv/src/test/java/tools/jackson/dataformat/csv/deser/TestParserNoSchema.java#L119-L146) · [Single-row regression](https://github.com/FasterXML/jackson-dataformats-text/blob/1600e2068acdb983ace981ff943aa4cdd0a2ac81/csv/src/test/java/tools/jackson/dataformat/csv/deser/MappingIteratorEnd9Test.java)

The original caller reproduced early exhaustion on the merge, official 3.3.0 and the `3.x` branch at `eb84c31b9dba`. With wrapping enabled, repeated lookahead returned true for both real rows, each had exactly one cell (`te,st`, then `x"y`), and both EOF checks returned false. An independent unwrapped token reader saw two complete arrays and both original cell values. Both supplemental controls agreed on the parent, merge, release and current branch. This corrects the challenge interpretation while preserving its original falsified prediction in the campaign score. [Original caller](../../../examples/409-jackson-csv-end-of-input/caller/PublicCaller.java) · [Two disambiguating controls](JacksonWrapping.java) · [Parent and merge observations](409-wrapping.json) · [Release and development observations](409.json)

```sh
python3 verification/merged-pr-links/upstream/recheck.py 409 --original-wrapping
```

The original-wrapping check uses the campaign's historical setup. The development builds compile the modules' production Java sources and include their resources. Avro's IDL parser is generated from the pinned grammar with ANTLR 4.13.2. Jackson's 3.4.0-SNAPSHOT CSV sources are compiled on the classpath against released 3.3.0 core and databind. The follow-up receipts cover 34 release and development JVMs and four additional historical Jackson JVMs. [Build and replay](recheck.py) · [Input lock](inputs.json)
