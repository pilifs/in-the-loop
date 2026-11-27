# Preserve metadata descriptions for properties Gradle leaves uncompiled

The merged incremental compile preserved the untouched description, replaced an edited comment and removed a deleted comment. The parent lost the untouched property’s description.

The original plugin and processor come from each pin. The consumer uses the same released Boot 4.0.7 configuration-properties annotation on both sides.

| Registered history | Public observation |
|---|---|
| Intent | The parent’s unchanged description was absent. The merge kept it. Both incremental compiles parsed only MoreProperties.java. |
| Control | Both clean builds parsed both sources and returned both current descriptions. |
| Challenge | The merged incremental and clean builds both removed the deleted description and kept the other one. |

`python3 examples/tools/build.py 597` checks the archived evidence. The original experiment can be repeated with the commands in the case record. [Case record](recorded-comparison.json) · [Claim registration](../../llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief.md) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50489)
