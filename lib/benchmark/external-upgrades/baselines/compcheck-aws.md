# CompCheck on the AWS maximum-date calibration

CompCheck’s stock registry contains the exact AWS production call to Joda-Time used when the public SDK parser processes the maximum-year input. The operator supplied callsite ID `c15-2`. It identifies `DateUtils.doParseISO8601Date(String)` at line 104 in `aws-java-sdk-core`, where the SDK parses the adjusted year through `DateTimeFormatter.parseMillis(String)`. The input comes from the published callsite registry. The developer’s regression test directly calls a different formatter method, `parseDateTime`. [AWS source line](https://github.com/compsuite-team/aws-sdk-java/blob/28f5c5f31ae04a20d9256f05bb306ecda5196867/aws-java-sdk-core/src/main/java/com/amazonaws/util/DateUtils.java#L104) · [CompCheck at the pinned revision](https://github.com/compsuite-team/CompCheck/tree/937d1d1495c4ff5449443183b70f465d1fe0b4d0)

| Input to the original API lookup | Knowledge records | Record for this exact API |
|---|---:|---|
| Stock published knowledge | 24 | AWS issue 233, `k15-1` |
| Stock knowledge with this AWS incident held out | 22 | None |

The held-out run removes `k14-1` and `k15-1`, the two same-client, same-version-pair issue-233 tests. The 22 surviving records retain their original order and content, including every other client. These are observed results of the pinned `findKnowledgeByAPI` function. The lookup alone makes no prediction about the return value of the public AWS parser. [Knowledge lookup and digests](compcheck-aws-lookup.json)

## Reproducing the stock command

The paired job invokes `python3 main.py --check --id c15-2` from `compcheck/` in a fresh process for each treatment. CompCheck uses its default `relax_prim_poly` strategy, 0.7 matching threshold and 60-second EvoSuite search budget. Both cases use Temurin 8.0.512+9, Maven 3.6.3, the same old client commit, separate fresh local Maven repositories, the two real Joda JARs and no external network during execution. The report records Maven diagnostics, successful context extraction, the match file and generated-test log counts separately from the Python process exit. [Runner](compcheck_aws.py) · [Verification job](../../../../verification/jobs/20261120-232916-compare-stock-compcheck-knowledge-on-aws.json)

Use an input directory containing the following publicly reproducible files. `aws.git` is a local Git database containing commit `28f5c5f31ae04a20d9256f05bb306ecda5196867`. The script obtains the stock callsite registry, knowledge and bundled Java tools from the archived CompCheck tree. The runner validates each downloaded binary by SHA-256.

- `compcheck.tar.gz` comes from the pinned repository. [GitHub source archive](https://codeload.github.com/compsuite-team/CompCheck/tar.gz/937d1d1495c4ff5449443183b70f465d1fe0b4d0)
- `aws.git` supplies the real project source. [AWS baseline commit](https://github.com/compsuite-team/aws-sdk-java/commit/28f5c5f31ae04a20d9256f05bb306ecda5196867)
- `apache-maven-3.6.3-bin.tar.gz` supplies the documented build tool. [Apache Maven 3.6.3](https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.6.3/apache-maven-3.6.3-bin.tar.gz)
- `joda-time-2.8.1.jar` and `joda-time-2.10.5.jar` supply the dependency pair. [Old release](https://repo.maven.apache.org/maven2/joda-time/joda-time/2.8.1/joda-time-2.8.1.jar) · [New release](https://repo.maven.apache.org/maven2/joda-time/joda-time/2.10.5/joda-time-2.10.5.jar)

```sh
python3 -I lib/benchmark/external-upgrades/baselines/compcheck_aws.py \
    --inputs "$INPUTS" --jdk "$JDK8" --output "$RESULT_JSON"
```
