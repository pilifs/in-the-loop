# Always-on Base64 XML names remain parseable across encodings

The writer emitted a legal underscore-prefixed Base64 name for the Chinese key. The JDK StAX reader and a fresh Jackson mapper recovered both sides of the adjacent Unicode boundary.

Both builds use the later timestamped Jackson 3.3.0 and annotations 2.23 snapshots listed in runtime.json.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws javax.xml.stream.XMLStreamException` | `{_5Lit5paH=cjk}/true` | matched |
| Control | `{YWJj=ascii}/true` | `{YWJj=ascii}/true` | matched |
| Challenge | `throws javax.xml.stream.XMLStreamException` | `{_0IA=at, z78=below}/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 567`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/FasterXML/jackson-dataformat-xml/pull/895)

Replacing the dated snapshots with Jackson Core 3.3.0 and annotations 2.23, plus Databind 3.3.0, reproduced all six returns or exceptions with the original caller bytes. [Pinned and released companion comparison](../../verification/merged-pr-links/r01-r50/followup-observations.json)
