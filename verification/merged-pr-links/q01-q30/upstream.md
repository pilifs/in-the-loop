# Spring Q-series release reproductions

All four counterexamples from the original comparisons also occurred on Spring Framework 7.1.0. Three used the identical compiled application caller. The fourth used the same retry fixture recompiled against the released package name. [Release observations](release-observations.json) · [Relocated and historical callers](followup-observations.json)

## Removing the second equal value

Given mutable maps containing a=x and b=x, capture the values of CollectionUtils.compositeMap(first, second). On 7.1.0 the first remove("x") returned true and left b=x. The second threw UnsupportedOperationException while b=x remained visible through that same view. Collection removal is an optional operation. The factory documents a partially unmodifiable map and specifically describes put and putAll. The question for maintainers is whether second-map removal through values should be supported or documented. [Both maps and the held view](../../../examples/513-spring-composite-map-values/README.md)

## The JDBC unlimited setting

Set a JdbcTemplate limit of zero over a driver that accepts Statement.setMaxRows(0) and supplies three ordered rows. List, callback, and stream queries all returned zero rows on 7.1.0. Leaving the default limit returned 11, 22, 33 through each query, and a limit of two returned 11, 22. The caller uses a physical H2 cursor and independently records each limit submitted to the statement. [All three query forms](../../../examples/520-spring-jdbc-row-limit/README.md) · [JDBC definition of zero](https://docs.oracle.com/en/java/javase/17/docs/api/java.sql/java/sql/Statement.html#setMaxRows(int))

## Reactive jitter overflow

Use a five-millisecond base delay and an immediately successful cold publisher. A 20-millisecond jitter returned ok on the first subscription. With jitter of 107000 days, adaptation synchronously threw ArithmeticException before any subscription. The 7.1.0 caller changes the historical import from org.springframework.aop.retry to org.springframework.resilience.retry. The latter implementation comes from spring-context. All three histories matched the original landing, including successful recovery after a genuine first failure. [Original caller](../../../examples/535-spring-reactive-retry-jitter/README.md) · [Release variant and input lock](followups.py)

## Direct legacy retry callbacks

Place a listener overriding the three-argument failure and success callbacks in CompositeRetryListener. Call those same overloads directly on the composite. The parent delivered E1 and R. The landing and 7.1.0 delivered neither. Invoking the same listener through RetryTemplate still delivered both. The newer state-aware and mixed-order composite controls also passed. [Old and new public callback histories](../../../examples/536-spring-retry-state-callbacks/README.md)

## Why the released JMS exchange differs

On the Q24 landing, a responder using JMSReplyTo alone returned ack-A on the owned queue. In 7.0.4 the template selects by JMSCorrelationID on an owned queue. With the unchanged responder, the receive timed out. After two calls, an independent consumer found the earlier ack-A ahead of its own marker C. This proves a reply had reached the queue. The temporary-queue control still received ack-A. [Original and released exchanges](../../../examples/531-spring-jms-reply-destination/README.md) · [7.0.4 selection code](https://github.com/spring-projects/spring-framework/blob/v7.0.4/spring-jms/src/main/java/org/springframework/jms/core/JmsTemplate.java)

Two additional 7.0.4 responders used the same in-process Artemis broker. One copied the provider-assigned request message ID into the reply’s correlation ID. The other echoed an explicit application correlation ID. Both received ack-A and ack-B, then read C from the same owned queue. This comparison isolates the reply selector on Artemis. The linked RabbitMQ report concerns a different provider and consumer creation order. [Both correlated controls](followup-observations.json) · [Original provider report](https://github.com/spring-projects/spring-framework/issues/36321)

## Reproduction

After preparing the Q-series cache, run the commands below. The release runner checks the original application class bytes. The follow-ups check the changed imports, the physical Spring providers, the two later factory class files, and the result of each control.

```sh
python3 verification/merged-pr-links/m01-m10/releases.py --inputs verification/merged-pr-links/q01-q30/release-inputs.json --fetch
python3 verification/merged-pr-links/q01-q30/check_releases.py
python3 verification/merged-pr-links/q01-q30/followups.py --fetch
```
