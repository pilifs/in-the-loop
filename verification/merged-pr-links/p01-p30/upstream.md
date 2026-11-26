# Spring release checks for P01–P30

Thirteen fresh JVMs ran the original callers on Spring Framework 7.1.0 from Maven Central. Each caller compiled to the same class bytes as in its historical comparison. All 13 outcomes agreed with the corresponding PR landing, including three counterexamples and a Jupiter diagnostic whose suggested remedy fails. The release lock identifies the Spring JARs by their published SHA-256 digests, the third-party dependencies by version and digest, and the loaded Spring provider for each history. [Release observations](release-observations.json) · [Input lock](release-inputs.json) · [Spring Framework artifacts](https://repo.maven.apache.org/maven2/org/springframework/spring-core/maven-metadata.xml)

## Empty entries in YAML

Load `{c: {}, e: []}` through a `YamlProcessor` subclass that calls the protected `getFlattenedMap(map, true, marker)` in its processing callback. Use a unique object as the marker and compare by identity. The result contained both keys. The empty map held the marker and the empty sequence held a blank string. Explicit null and tilde both retained the marker, and a quoted empty scalar remained a string. The hook documents the parameter as the value for empty entries. The reportable question is whether callers should be able to select that value for an empty sequence too. [Upstream declaration](https://github.com/spring-projects/spring-framework/blob/ab314aadd95e05318629943754a8e4c1dd0400be/spring-beans/src/main/java/org/springframework/beans/factory/config/YamlProcessor.java) · [Reproduction and controls](../../../examples/481-spring-yaml-empty-values/README.md)

## Copying a subclass’s mail date

Override only `SimpleMailMessage.getSentDate()` to return a fresh `Date(1234)` and leave the inherited date field unset. The public getter returned 1234 ms. The copy constructor produced a null date, and `copyTo` left an existing target date at 77 ms. Both copy paths honored the overridden getter on the PR parent. The landing and 7.1.0 also passed the original plain-message tests for protection against external mutation. [Caller, recording target and results](../../../examples/484-spring-mail-date-copy/README.md)

## Physical line framing for protobuf

Select `application/jsonl` with the default `ProtobufJsonEncoder` and encode a two-item Flux of generated protobuf messages containing nested fields. Split the complete UTF-8 output at LF. There were 12 physical lines, and a protobuf JSON parser rejected each individual line. Supplying a compact printer on the same encoder produced exactly two terminated lines, each decoding to its original message in order. [Encoder implementation](https://github.com/spring-projects/spring-framework/blob/a8b48a6042c80a66c6237b35d29db84c45c75bd2/spring-web/src/main/java/org/springframework/http/codec/protobuf/ProtobufJsonEncoder.java) · [Minimal caller and line readback](../../../examples/489-spring-protobuf-json-lines/README.md)

## Disabling parallelism in a recording Jupiter test

Declare `@RecordApplicationEvents`, `@TestInstance(PER_CLASS)` and `@Execution(CONCURRENT)`. Launch the same class with the Jupiter engine twice. Setting `junit.jupiter.execution.parallel.enabled` to either `true` or `false` failed the container with `IllegalStateException`. The diagnostic in the released SpringExtension still suggests disabling parallel execution altogether. Changing the global switch alone therefore does not achieve the suggested remedy for this annotated class. Ordinary parent- and child-thread recordings passed. [Engine fixture and both configuration results](../../../examples/504-spring-child-thread-events/README.md)

## Historical JDBC compatibility

The same application binary called the public three-argument `ScriptUtils.readScript` successfully on Spring JDBC 5.1.4.RELEASE and raised `NoSuchMethodError` on 5.1.5.RELEASE. The source was compiled against the parent and the invocation descriptor was checked with javap. A separate comparison of `ResourceDatabasePopulator` executed the two intended inserts on the later release. With the original SQL and 5.1.4, the first insert was already durable when the second statement failed. [Direct client and independent database reads](../../../examples/493-spring-sql-comment-lines/README.md) · [Historical release results](historical-observations.json)

## Reproduction

From a checkout with the prepared campaign cache, run the following commands. Each release comparison recompiles the original callers and checks the class origins. The last command checks the versions, digests, exact outcomes and comparison side for every history.

```sh
python3 verification/merged-pr-links/m01-m10/releases.py --inputs verification/merged-pr-links/p01-p30/release-inputs.json --fetch
python3 verification/merged-pr-links/m01-m10/releases.py --inputs verification/merged-pr-links/p01-p30/historical-inputs.json --output "$TMPDIR/p30-historical.json"
python3 verification/merged-pr-links/p01-p30/check_releases.py --historical "$TMPDIR/p30-historical.json"
```
