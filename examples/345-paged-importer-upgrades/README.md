# An unchanged importer across two dependency upgrades

Commons IO repaired the bytes delivered after a preview and implicit reset. Commons CSV repaired pagination when the displayed record number started above one. Only the installation with both repairs returned every complete page correctly. The application was compiled once. Each cell ran in its own JVM on 96 inputs, using a fresh stream for the byte observation. [Compiled class hashes and loaded JARs](records/matrix/matrix.json)

| Runtime Commons IO | Runtime Commons CSV | Wrong bytes | Wrong count | Wrong numbered page |
|---|---|---:|---:|---:|
| Parent | Parent | 48 | 40 | 68 |
| Fix | Parent | 0 | 40 | 40 |
| Parent | Fix | 48 | 0 | 48 |
| Fix | Fix | 0 | 0 | 0 |

For the two-row document `a,b\nc,d\n`, preview the first byte, reset without a mark, and request one row starting at record 2. Both installations with the CSV parent return an empty page. That masks the IO error. With CSV fixed and IO old, the count is correct, but record 2 has three fields, `["a","ba","b"]`. With both fixes it has the expected two fields, `["a","b"]`. The four installations also passed every positive control with preview disabled and starting number 1. [Four complete JVM observation streams](records/matrix) · [Independent literal oracle](controls/table.json)

The two CSV revisions were built separately against their declared Commons IO 2.22.0 and Commons Codec 1.22.0. At runtime, each cell loaded one selected IO JAR and one selected CSV JAR. Codec stayed fixed. The full Maven builds record their clean revisions, first-parent checks, compiler, resolved inputs and product hashes. [Build records](records/builds) · [Public proof tasks](target.json) · [Frozen obligations](milestones.json)
