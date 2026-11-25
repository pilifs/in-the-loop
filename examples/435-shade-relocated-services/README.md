# Maven Shade packages two service providers under the relocated interface

The pinned Maven goal failed with duplicate service descriptors on the parent. The fix packaged one relocated interface descriptor in both input orders. An isolated ServiceLoader instantiated both providers from the artifact.

A fresh Maven project runs the plugin goal offline with a private fixture repository. Its child class-loading trace must identify the exact copied transformer JAR before a packaging outcome is accepted.

| Question | Input |
|---|---|
| Intent | Package A and B together with the stated relocation. |
| Control | Package A alone with the same transform. |
| Challenge | Load the merged artifact in a fresh class loader with no fixture classes supplied by its parent. Resolve borg.foo.Svc there and iterate ServiceLoader.load(serviceClass, loader). Repeat with the two input artifacts presented in the opposite order. |

Run `python3 examples/tools/build.py 435` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pin-goal. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/maven-shade-plugin/pull/150) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
