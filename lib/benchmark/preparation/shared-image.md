# R3: a small compare run's time by stage

The joint example's builds (examples 190, 191), medians of 7 repeats, a release build; for these fixtures only.

## Compilation (javac)

| Build | ms |
|---|---|
| the Spring stand-ins | 601.8 |
| before | 395.1 |
| after | 404.1 |
| offset | 402.4 |

## Repeated stages, one by one

| Stage | ms |
|---|---|
| decoding every class file of the old build (4 files, 4988 bytes) | 0.03 |
| relocating the old build into package before/ (each proof does once) | 0.12 |
| loading both builds for alignment (compare does once) | 0.08 |
| aligning the two builds (compare does once) | 0.20 |
| reading both builds' entry points' observation specs (compare does once) | 0.62 |
| opening the JDK's image the first time in a process, its table of classes built, writing the copy of its index included (each open did before R3's cache) | 7.89 |
| opening the JDK's image again, its table shared (each class path with the JDK does: several per proof) | 0.06 |
| writing the models' 17 class files into a work directory (each proof does once, after its lookup) | 0.27 |
| the models' digest (each claim key takes it) | 0.09 |
| the binary's digest (12926816 bytes; once per process) | 37.31 |

## The runs

### cold (`after`)

5 proofs, 0 exact hits; in process 65.6 ms, as a process 125.0 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 6.1 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 0.9 |
| key's closures: both versions' closures digested | 1.2 |
| lookup: reading the store | 0.0 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 47.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 8.9 |
| store: writing the result, a refutation's witness replayed first | 0.6 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.7 |

### unchanged rerun (`after`)

5 proofs, 5 exact hits; in process 8.6 ms, as a process 66.1 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 5.4 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 0.8 |
| key's closures: both versions' closures digested | 1.1 |
| lookup: reading the store | 0.1 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.7 |

### defect, cold (`offset`)

5 proofs, 0 exact hits; in process 1575.8 ms, as a process 1640.1 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 48.4 |
| plan: both versions' reach and closures compared | 0.6 |
| key: the claim and its digest | 1.0 |
| key's closures: both versions' closures digested | 1.3 |
| lookup: reading the store | 0.0 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 1484.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 35.8 |
| store: writing the result, a refutation's witness replayed first | 1.8 |
| replay of a stored or new witness (inside lookup and store) | 0.9 |
| outside every proof: compare's own steps after the last proof | 0.8 |

### defect, rerun (`offset`)

5 proofs, 5 exact hits; in process 31.9 ms, as a process 106.4 ms (medians of 7)

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 27.3 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.0 |
| key's closures: both versions' closures digested | 1.2 |
| lookup: reading the store | 0.2 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.7 |
| outside every proof: compare's own steps after the last proof | 0.7 |
