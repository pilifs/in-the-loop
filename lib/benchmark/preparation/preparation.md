# R3: a small compare run's time by stage

The joint example's builds (examples 190, 191), medians of 7 repeats, a release build; for these fixtures only.

## Compilation (javac)

| Build | ms |
|---|---|
| the Spring stand-ins | 636.4 |
| before | 403.2 |
| after | 429.3 |
| offset | 412.9 |

## Repeated stages, one by one

| Stage | ms |
|---|---|
| decoding every class file of the old build (4 files, 4988 bytes) | 0.03 |
| relocating the old build into package before/ (each proof does once) | 0.14 |
| loading both builds for alignment (compare does once) | 0.09 |
| aligning the two builds (compare does once) | 0.22 |
| reading both builds' entry points' observation specs (compare does once) | 12.76 |
| opening the JDK's image, lib/modules (each class path with the JDK does: several per proof) | 6.26 |
| writing the models' 17 class files into a work directory (each proof does once, after its lookup) | 0.32 |
| the models' digest (each claim key takes it) | 0.09 |
| the binary's digest (12900080 bytes; once per process) | 35.69 |

## The runs

### cold (`after`)

5 proofs, 0 exact hits; in process 460.6 ms, as a process 496.1 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 207.8 |
| plan: both versions' reach and closures compared | 0.8 |
| key: the claim and its digest | 1.3 |
| key's closures: both versions' closures digested | 1.5 |
| lookup: reading the store | 0.1 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 55.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 161.7 |
| store: writing the result, a refutation's witness replayed first | 1.0 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 31.2 |

### unchanged rerun (`after`)

5 proofs, 5 exact hits; in process 209.8 ms, as a process 290.3 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 185.4 |
| plan: both versions' reach and closures compared | 0.8 |
| key: the claim and its digest | 1.2 |
| key's closures: both versions' closures digested | 1.5 |
| lookup: reading the store | 0.3 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 20.4 |

### defect, cold (`offset`)

5 proofs, 0 exact hits; in process 2217.2 ms, as a process 2215.9 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 245.3 |
| plan: both versions' reach and closures compared | 0.9 |
| key: the claim and its digest | 1.3 |
| key's closures: both versions' closures digested | 1.5 |
| lookup: reading the store | 0.0 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 1723.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 197.5 |
| store: writing the result, a refutation's witness replayed first | 15.6 |
| replay of a stored or new witness (inside lookup and store) | 14.4 |
| outside every proof: compare's own steps after the last proof | 29.9 |

### defect, rerun (`offset`)

5 proofs, 5 exact hits; in process 265.3 ms, as a process 491.1 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 222.5 |
| plan: both versions' reach and closures compared | 0.9 |
| key: the claim and its digest | 1.4 |
| key's closures: both versions' closures digested | 1.5 |
| lookup: reading the store | 0.4 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 13.8 |
| outside every proof: compare's own steps after the last proof | 23.1 |
