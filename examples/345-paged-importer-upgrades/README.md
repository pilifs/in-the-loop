# An unchanged importer across two dependency upgrades

Commons IO repaired the bytes delivered after a preview and implicit reset. Commons CSV repaired pagination when the displayed record number started above one. Only the installation with both repairs returned every complete page correctly. The application was compiled once. Each cell ran in its own JVM on 96 inputs, using a fresh stream for the byte observation. [Compiled class hashes and loaded JARs](records/matrix/matrix.json)

| Runtime Commons IO | Runtime Commons CSV | Wrong bytes | Wrong count | Wrong numbered page |
|---|---|---:|---:|---:|
| Parent | Parent | 48 | 40 | 68 |
| Fix | Parent | 0 | 40 | 40 |
| Parent | Fix | 48 | 0 | 48 |
| Fix | Fix | 0 | 0 | 0 |

For the two-row document `a,b\nc,d\n`, preview the first byte, reset without a mark, and request one row starting at record 2. Both installations with the CSV parent return an empty page. That masks the IO error. With CSV fixed and IO old, the count is correct, but record 2 has three fields, `["a","ba","b"]`. With both fixes it has the expected two fields, `["a","b"]`. The four installations also passed every positive control with preview disabled and starting number 1. [Four complete JVM observation streams](records/matrix) · [Independent literal oracle](controls/table.json)

Strict native checking established five of the twelve primary claims and refuted seven. Each refutation reproduced on the original JVM entry. The fixed/fixed complete-page proof covers all 96 selectors. All four positive controls also have native proofs. The verifier checked the actual compiled calls under the pinned stock JDK, including the stream reset, UTF-8 decoder, CSV iterator and collection of fields. The receipts assume successful JDK initialization and permitted reads from the standard system properties table. The decoder check covers the property values that determine its lock policy. [Fixed/fixed native page proof](records/native-selectors/fix-fix/20261120T215140Z-1f55ccae/tasks/page-fix-fix/result.json) · [All twelve dispositions](../../verification/next-proof-campaign-results.json)

The two CSV revisions were built separately against their declared Commons IO 2.22.0 and Commons Codec 1.22.0. At runtime, each cell loaded one selected IO JAR and one selected CSV JAR. Codec stayed fixed. The full Maven builds record their clean revisions, first-parent checks, compiler, resolved inputs and product hashes. [Build records](records/builds) · [Public proof tasks](target.json) · [Frozen obligations](milestones.json)

### What an upgrade costs

Each update starts from the same parent/parent evidence. The inline check runs the whole importer. The composed check first obtains the remaining bytes and decoded UTF-16 from 24 stream inputs, then checks CSV for each distinct text, start and cap. Both strategies produce the same 96 complete observations as a fresh JVM for each configuration. The byte client loads IO alone. The CSV stage binds IO, CSV and Codec, so changing IO also rechecks CSV on every newly reachable parser input. [Measured runs and cache keys](records/composition.json)

| Update | Inline inputs checked / reused | IO inputs checked / reused | CSV inputs checked / reused | Inline wall | Composed wall |
|---|---:|---:|---:|---:|---:|
| Clean parent/parent | 96 / 0 | 24 / 0 | 36 / 0 | 2.408 s | 3.502 s |
| Unchanged | 0 / 96 | 0 / 24 | 0 / 36 | 0.093 s | 0.095 s |
| IO only | 96 / 0 | 24 / 0 | 12 / 0 | 0.226 s | 0.269 s |
| CSV only | 96 / 0 | 0 / 24 | 36 / 0 | 0.257 s | 0.208 s |
| Unused class only | 96 / 0 | 0 / 24 | 0 / 36 | 0.228 s | 0.106 s |
| Both fixes | 96 / 0 | 24 / 0 | 12 / 0 | 0.114 s | 0.198 s |

The cold finite-JVM runs include application preparation (2.100 s inline, 3.225 s composed), checking (0.122 s, 0.173 s) and independent witness replay (0.092 s, 0.091 s). Peak child-process RSS was 122.6 MiB and 120.7 MiB respectively. The IO repair removes the duplicate-prefix inputs, reducing the reachable CSV cases from 36 to 12. Changing an unrelated class gives the application a new classpath identity and preserves both isolated producer results. [Byte and decoder evidence](../338-commons-io-bom-reset/records/importer-facts.json) · [CSV evidence](../339-commons-csv-page-numbers/records/importer-facts.json)

The native byte-preview client also ran with IO as its only dependency. A CSV-only change reused its entire proof and took 0.084 s including JVM witness replay. Rechecking the byte observation on the full application classpath took 0.437 s. An IO upgrade required a new proof on both classpaths. Every cache decision agreed with a separate clean native execution. [Native byte-preview measurements](records/native-preview/20261120T220835Z-91167742/result.json)
