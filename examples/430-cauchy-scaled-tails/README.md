# Commons Statistics computes representable scaled Cauchy tail quantiles

The two ordinary tails became distinct and accurate. A small scale with a subnormal probability still returned two infinities despite finite, representable reference answers.


| Question | Input |
|---|---|
| Intent | Use p=1e-20 and p=1e-300 on the same distribution. |
| Control | Use p=0, 0.5, 1 in increasing order. |
| Challenge | On the merge use of(0, 2⁻¹⁰⁰) with the exactly representable positive p=2⁻¹⁰⁵⁰. Observe both public inverse methods. |

Run `python3 examples/tools/build.py 430` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/commons-statistics/pull/140) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

The finite scaled tail returned infinities on master at 8381f56aa3ec. Release 1.3 predates the repair and returns a different wrong finite result for the same input. [Release and development evidence](../../verification/merged-pr-links/l01-l20/upstream/README.md)
