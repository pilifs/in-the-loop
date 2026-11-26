# R-series findings for upstream review

## Commons IO marks and skips

Wrap a StringReader containing `012345` in a BoundedReader with maximum five and call `mark(2)`. Three ordinary reads yield `0`, `1`, then EOF. On a fresh otherwise identical reader, `skip(4)` returns four and a direct read from the retained delegate returns `4`. The merged PR describes a mark limit on skips. Its global cap does work, including when the delegate skips less than the requested count. The mark behavior also occurs on the parent. [Caller and both JVM outcomes](../../../examples/549-commons-bounded-reader-skip/README.md)

## Avro big-decimal buffer slices

Encode 7 and 12.30 independently with BigDecimalConversion. Concatenate the two encodings and take a heap ByteBuffer slice containing only the second. A standalone copy of those remaining bytes decodes as unscaled 1230 with scale two. The slice decodes as unscaled 7 with scale zero. Both reads use the same schema and a converter separate from the encoder. The merged converter passes the full backing array to the decoder. [Independent buffer views and original revisions](../../../examples/574-avro-big-decimal-slice/README.md)

## Resilience4j retry notifications

An asynchronous supplier returns a completed stage containing `again`. Configure the result predicate to retry on that value, a negative interval, and three possible attempts. The completed result is `again`, and the supplier runs once. A retry listener nevertheless receives a retry event with a wait of −1 ms. Compare the exceptional stop on the merge, which publishes an error after the preceding zero-delay retry. The result-path notification appears on both revisions. [Supplier, events and positive control](../../../examples/582-resilience-async-stop-event/README.md)

## AssertJ record accessor precedence

Compare two records with different string components, equal booleans, and a JavaBeans getter that returns the same constant. The default recursive equality assertion passes on the landing. Calling the component accessors directly gives `one` and `two`. Removing the constant getter lets the merged assertion distinguish the strings. This is a question about the documented choice of accessor for a record with a JavaBeans getter. [Both record definitions and default assertions](../../../examples/585-assertj-record-accessor-order/README.md)

## What reproduced on published versions

- **Commons IO 2.22.0** returned four from the marked skip and left the delegate on character `4`. The global-bound behavior in this release matched the original parent. [Release measurements](release-observations.json)
- **Avro 1.11.4 and 1.12.0** decoded the prefixed slice as 7 and the independent copy as 12.30. The same logical value decoded normally from an ordinary heap buffer, raised ReadOnlyBufferException from a read-only buffer and raised UnsupportedOperationException from a direct buffer. The caller preserved the input bytes across these storage variations. Avro 1.11.3 lacked the logical conversion. [View construction](DecimalViews.java) · [Release and view outcomes](followup-observations.json)
- **Resilience4j 2.2.0** delivered the negative-delay retry notification. In 2.1.0 the stage returned the same value after a single call with zero retry events. Both releases accepted the positive-delay control. [Version-specific event and oracle](check_releases.py) · [Release measurements](release-observations.json)
- **AssertJ 3.27.1** distinguished the ordinary record component but accepted equality when the constant JavaBeans getter was present. The getter also took precedence in 3.27.0, where the ordinary record fixture still missed the unequal component. Maintainers can decide whether the default policy should prefer record components or document the precedence. [Release measurements](release-observations.json)

## Mark position shortens a fresh Commons IO read window

Use a fresh BoundedReader over `abcdefg` with a global maximum of six. At starting positions zero, one and two, call `mark(2)` and read until the wrapper returns EOF. The three post-mark strings were `ab`, `b` and the empty string. The delegate’s next character was `c` each time. A reset allowed `a`, `b` and EOF respectively. Each stream had at least two characters of global allowance at its mark. The results agreed on 2.22.0 and both PR pins. This case uses only ordinary reads after marking. It can be reported independently of the skip discrepancy. [Three positions and independent delegate reads](MarkWindow.java) · [Measured results](followup-observations.json)
