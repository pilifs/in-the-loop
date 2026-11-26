# Three challenges on Spring Framework 7.0.10

The same caller bytecode used for the historical comparisons ran all nine histories on the published Spring Framework 7.0.10 modules. Each Spring JAR matched Maven Central's published checksum. The release input lock pins each JAR and third-party dependency by SHA-256. Each history used a fresh JVM. [Release observations](release-observations.json) · [Artifact and JDK lock](release-inputs.json) · [Spring release artifacts](https://repo.maven.apache.org/maven2/org/springframework/)

## Server-sent event retry hints

Feed a finite WebClient event stream either `"retry: 25\ndata:foo\n\n"` or `"retry:25 \ndata:foo\n\n"`. Read the event's payload and retry duration. The parser may discard one leading space from a field value. A retry value must then consist entirely of ASCII digits. The trailing space leaves the second field ineligible to set a retry delay. [W3C event-stream field rules, §7](https://www.w3.org/TR/2015/REC-eventsource-20150203/#event-stream-interpretation)

On both the PR landing and 7.0.10, both inputs emitted `foo`, set a 25 ms delay and completed. The challenge therefore reproduces on the release. A separate malformed value, `retry:none`, illustrates the difference between these deployments. The landing delivered both events. Release 7.0.10 ended with WebClientResponseException caused by NumberFormatException, as the PR parent did. [Minimal caller](../../../examples/466-spring-sse-retry/caller/PublicCaller.java) · [Historical comparison](../../../examples/466-spring-sse-retry/README.md)

## Strict R2DBC constructor mapping

Map an H2 row with the single column `name='Ada'` to a class whose constructor uppercases the name and whose setter preserves its spelling. On the PR landing the default mapper returned `ADA`. Calling `setCheckFullyPopulated(true)` and mapping the same complete row raised InvalidDataAccessApiUsageException. The bean and record controls both read their expected values on 7.0.10. [Caller and historical results](../../../examples/470-spring-r2dbc-mappers/README.md)

Spring removed the strict setter in commit `ae3bc378d650` on 15 August 2023. Inspection of the released BeanPropertyRowMapper confirms that the setter is absent, and running the original binary challenge on 7.0.10 raised NoSuchMethodError. The original strict-mode finding is historical. [Upstream API removal](https://github.com/spring-projects/spring-framework/commit/ae3bc378d650daa70c2f901a511ad8c96b4f6faf) · [Release observations](release-observations.json)

## JMS replacement after direct reinitialization

Configure SingleConnectionFactory with reconnect-on-exception and a provider supplying A, B and C. A and C accept a listener. B throws a designated JMSException during listener installation. Begin with a successful A connection, call public `initConnection()`, catch B's exception and request a session through a fresh logical connection. A closed physical connection rejects that session in the provider. [Recording provider and application caller](../../../examples/475-spring-jms-replacement/caller/PublicCaller.java)

On both the PR landing and 7.0.10, the factory closed A and B, then tried to create the session on closed A. It never requested C. The same provider with an explicit `resetConnection()` first recovered on C. Ordinary logical handles shared one healthy A. This identifies the direct reinitialization path and gives the two comparison histories for an upstream report. [Historical observations](../../../examples/475-spring-jms-replacement/README.md) · [Release observations](release-observations.json)

## Reproduction

With the prepared Spring campaign cache, run the following command from the checkout. The first run can fetch missing release JARs from Maven Central. Subsequent runs can use the same cache offline.

```sh
python3 verification/merged-pr-links/m01-m10/releases.py \
  --inputs verification/merged-pr-links/o01-o20/release-inputs.json --fetch
```
