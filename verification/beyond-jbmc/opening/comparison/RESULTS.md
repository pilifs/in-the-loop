# Historical 187 at opening

The programs and statements match the original November 7 inputs. Every stock target and post-call control used the packaged Ubuntu 24.04 JBMC 6.11.0 model JAR. Proof credit requires complete reported properties and a failing post-call control with its normal-return input reproduced on the JVM. A target refutation requires that its own input reproduce the failure on the original JVM. A stock proof contradicted on its own public caller is recorded as incorrect.

| Native against | Both | Native only | Comparator only | Neither |
|---|---:|---:|---:|---:|
| integrated | 147 | 32 | 0 | 8 |
| stock | 143 | 36 | 1 | 7 |
| either | 153 | 26 | 1 | 7 |

| Disposition | Strict native | Integrated staged | Standalone stock |
|---|---:|---:|---:|
| gap | 6 | 18 | 0 |
| incorrect proof | 0 | 0 | 12 |
| incorrect refutation | 0 | 0 | 26 |
| no property report | 0 | 0 | 2 |
| out of memory | 0 | 1 | 0 |
| post-call input unconfirmed on JVM | 0 | 0 | 1 |
| proved | 94 | 71 | 70 |
| refused | 2 | 9 | 0 |
| refuted | 85 | 76 | 74 |
| timeout | 0 | 5 | 2 |
| witness not reproduced | 0 | 7 | 0 |

| Matched correct pairs | Count | Median wall s, native / comparator | Median CPU s | Median peak MiB |
|---|---:|---:|---:|---:|
| integrated | 147 | 0.021 / 0.254 | 0.020 / 0.178 | 52.500 / 52.500 |
| stock | 143 | 0.021 / 0.092 | 0.020 / 0.087 | 52.500 / 53.200 |

Costs cover the target checker processes, including children. The stock reach control and JVM adjudication are additional work. The full 187 rows retain capped times and incomplete reports. Proof caches were disabled. Host page cache state was unmeasured. [Row-level outcomes and disagreements](matrix.json.gz)
