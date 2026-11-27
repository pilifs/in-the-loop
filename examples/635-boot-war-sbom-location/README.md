# An executable Maven WAR advertises its embedded SBOM

Checks the format, physical WAR location and actual SBOM bytes, with a differently located CycloneDX filename encountered first.

The numbered caller exercises the shared original Repackager. The Maven goal’s independent fixture is accounted for in the campaign evidence.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `absent/absent:present` | `CycloneDX/WEB-INF/classes/META-INF/sbom/application.cdx.json:selected` | matched |
| Control | `CycloneDX/META-INF/sbom/application.cdx.json` | `CycloneDX/META-INF/sbom/application.cdx.json` | matched |
| Challenge | `absent/absent:present` | `CycloneDX/WEB-INF/classes/META-INF/sbom/application.cdx.json:selected` | matched |

Replay with `python3 examples/tools/build.py 635` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51551)
