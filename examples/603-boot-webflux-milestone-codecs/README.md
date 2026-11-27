# Shared WebFlux JSON codecs across server and clients

Both original Boot source slices compiled on one reconstructed July 2017 codec profile. The parent emitted firstName and read a snake-case POST as null. The merge emitted first_name, decoded Lin, and both injected clients decoded Mia.

Six unmodified Framework codec configuration sources from 2ccbc55ffdff supply the historical method names. Boot 2.0.0.M2 supplies unchanged dependencies, Framework RC3 supplies the remaining HTTP classes, and Jackson 2.9.0.pr4 supplies the nonblocking parser. All JAR and source digests and the original loaded providers are recorded.

The July 2017 published snapshot binaries are unavailable. The earlier parent-slice/M3 release comparison is retained as a separate profile.

| Public history | Original parent | Original merge |
|---|---|---|
| GET and POST with snake-case naming | firstName=Ada, POST returned null | first_name=Ada, POST returned Lin |
| Default mapper GET | firstName=Ada | firstName=Ada |
| Decode fixed bytes in both clients | Outside the registered scope | WebClient and WebTestClient each returned Mia |

The two raw-server histories use the same caller bytecode. The merge-only client calls bind the original Boot client configurations in the JVM. [Loaded classes and observations](../../verification/merged-pr-links/s01-s50/webflux-2017/reconstructed-observations.json) · [Pinned Framework source and dependency graph](../../verification/merged-pr-links/s01-s50/webflux-2017/reconstruction-inputs.json) · [Separate release comparison](../../verification/merged-pr-links/s01-s50/webflux-2017/observations.json) · [Reproduction commands](recorded-comparison.json)
