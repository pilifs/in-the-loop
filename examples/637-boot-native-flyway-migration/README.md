# Execute the Flyway migration found in a native image subdirectory

Six GraalVM executables distinguish a root migration from nested ones. All three merged images applied version 2 once with checksum −391086276 and a durable marker of 73.

Every native executable has a fresh resource layout and H2 database. Its ordinary and Spring AOT JVM controls applied the SQL independently. The full native compilation belongs in the verification pipeline.

| Registered history | Public observation |
|---|---|
| Intent | The native parent failed opening a flattened migration path. The merged image applied the nested SQL and returned the row. |
| Control | Both root-level native images applied version 2 with the same checksum and row. |
| Challenge | Both merged nested layouts applied version 2 exactly once with identical checksum and JDBC values. |

`python3 examples/tools/build.py 637` checks the archived evidence. The original experiment can be repeated with the commands in the case record. [Case record](recorded-comparison.json) · [Claim registration](../../llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief.md) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50433)
