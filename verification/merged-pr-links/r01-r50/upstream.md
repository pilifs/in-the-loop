# R-series findings for upstream review

## Commons IO marks and skips

Wrap a StringReader containing `012345` in a BoundedReader with maximum five and call `mark(2)`. Three ordinary reads yield `0`, `1`, then EOF. On a fresh otherwise identical reader, `skip(4)` returns four and a direct read from the retained delegate returns `4`. The merged PR describes a mark limit on skips. Its global cap does work, including when the delegate skips less than the requested count. The mark behavior also occurs on the parent. [Caller and both JVM outcomes](../../../examples/549-commons-bounded-reader-skip/README.md)

## Avro big-decimal buffer slices

Encode 7 and 12.30 independently with BigDecimalConversion. Concatenate the two encodings and take a heap ByteBuffer slice containing only the second. A standalone copy of those remaining bytes decodes as unscaled 1230 with scale two. The slice decodes as unscaled 7 with scale zero. Both reads use the same schema and a converter separate from the encoder. The merged converter passes the full backing array to the decoder. [Independent buffer views and original revisions](../../../examples/574-avro-big-decimal-slice/README.md)

## Resilience4j retry notifications

An asynchronous supplier returns a completed stage containing `again`. Configure the result predicate to retry on that value, a negative interval, and three possible attempts. The completed result is `again`, and the supplier runs once. A retry listener nevertheless receives a retry event with a wait of −1 ms. Compare the exceptional stop on the merge, which publishes an error after the preceding zero-delay retry. The result-path notification appears on both revisions. [Supplier, events and positive control](../../../examples/582-resilience-async-stop-event/README.md)

## AssertJ record accessor precedence

Compare two records with different string components, equal booleans, and a JavaBeans getter that returns the same constant. The default recursive equality assertion passes on the landing. Calling the component accessors directly gives `one` and `two`. Removing the constant getter lets the merged assertion distinguish the strings. This is a question about the documented choice of accessor for a record with a JavaBeans getter. [Both record definitions and default assertions](../../../examples/585-assertj-record-accessor-order/README.md)
