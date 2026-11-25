# Agrona copies cursor-backed map entries into arrays

| History | Observed result |
|---|---|
| Intent | Both array overloads returned one cursor three times on each of the four parent maps. Every merged array held all three original pairs as distinct entries of the requested array type. |
| Control | Disabling allocation avoidance preserved the three pairs on both revisions. |
| Challenge | The three merged entries compared equal to their JDK counterparts but all hashed to 11. HashSet found 1=10 and missed 2=20 and 3=30. |

The backing map remains unchanged. Pair multisets are sorted only after the conversions finish. Reference hashes from SimpleImmutableEntry were 11, 22 and 29.

Run `python3 examples/tools/build.py 448` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/aeron-io/agrona/pull/202) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)

The same three-entry HashSet lookup missed keys 2 and 3 on Agrona 1.4.0 and 2.7.2. Each release used the historical caller bytecode on JDK 17. [Release evidence](../../verification/merged-pr-links/m01-m10/upstream.md)
