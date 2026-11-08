# R3 and J4: a small compare run's time by stage

The joint example's builds (examples 190, 191) and two edits of `after` (`lib/tests/fixtures/preparation`), medians of 7 repeats, a release build; for these fixtures only.

## Compilation (javac)

| Build | ms |
|---|---|
| the Spring stand-ins | 569.2 |
| before | 358.2 |
| after | 375.1 |
| offset | 370.8 |
| unrelated-edit | 377.9 |
| helper-rewrite | 381.5 |

## Repeated stages, one by one

| Stage | ms |
|---|---|
| decoding every class file of the old build (4 files, 4988 bytes) | 0.03 |
| relocating the old build into package before/ (each proof does once) | 0.14 |
| loading both builds for alignment (compare does once) | 0.08 |
| aligning the two builds (compare does once) | 0.20 |
| reading both builds' entry points' observation specs (compare does once) | 0.99 |
| opening the JDK's image the first time in a process, its table of classes built, writing the copy of its index included (each open did before R3's cache) | 7.70 |
| opening the JDK's image again, its table shared (each class path with the JDK does: several per proof) | 0.07 |
| writing the models' 17 class files into a work directory (each proof does once, after its lookup) | 0.27 |
| the models' digest (each claim key takes it) | 0.09 |
| the binary's digest (13683856 bytes; once per process) | 38.34 |

## The runs

### cold (`after`, from an empty proof cache)

5 proofs, 0 exact hits, 5 proved; in process 62.9 ms, as a process 119.3 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | proved |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | proved |  |
| shop.Pricing#total | proved | Pricing.discount sha256:1ac7558b1eb3740fcf9b33b0cbe9820064479918fbc7ea97c7c758d585187ade |
| shop.Pricing#withQuantity | proved |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 6.2 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.1 |
| key's closures: both versions' closures digested | 1.1 |
| lookup: reading the store | 0.0 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 44.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 9.2 |
| store: writing the result, a refutation's witness replayed first | 0.5 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.8 |

### unchanged rerun (`after`, from the cache the same build's run left)

5 proofs, 5 exact hits, 0 proved; in process 9.2 ms, as a process 63.2 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | exact hit |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | exact hit |  |
| shop.Pricing#total | exact hit | Pricing.discount sha256:1ac7558b1eb3740fcf9b33b0cbe9820064479918fbc7ea97c7c758d585187ade |
| shop.Pricing#withQuantity | exact hit |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 5.7 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.1 |
| key's closures: both versions' closures digested | 1.1 |
| lookup: reading the store | 0.1 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.7 |

### unrelated edit (`unrelated-edit`, from a copy of the cache a cold run of `after` left)

5 proofs, 5 exact hits, 0 proved; in process 9.3 ms, as a process 62.9 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | exact hit |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | exact hit |  |
| shop.Pricing#total | exact hit | Pricing.discount sha256:1ac7558b1eb3740fcf9b33b0cbe9820064479918fbc7ea97c7c758d585187ade |
| shop.Pricing#withQuantity | exact hit |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 5.9 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.1 |
| key's closures: both versions' closures digested | 1.1 |
| lookup: reading the store | 0.1 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.7 |

### safe helper rewrite (`helper-rewrite`, from a copy of the cache a cold run of `after` left)

5 proofs, 1 exact hits, 4 proved; in process 71.1 ms, as a process 126.5 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | proved |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | proved |  |
| shop.Pricing#total | proved | Pricing.discount sha256:27742bcf676d8eb3941e3ec75e40b61744745c9b6c3315241609e8d90a4b1cc5 |
| shop.Pricing#withQuantity | exact hit |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 6.4 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.2 |
| key's closures: both versions' closures digested | 1.2 |
| lookup: reading the store | 0.1 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 52.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 8.6 |
| store: writing the result, a refutation's witness replayed first | 0.4 |
| replay of a stored or new witness (inside lookup and store) | 0.0 |
| outside every proof: compare's own steps after the last proof | 0.8 |

### defect, cold (`offset`, from an empty proof cache)

5 proofs, 0 exact hits, 5 proved; in process 1439.2 ms, as a process 1500.6 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | proved |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | proved |  |
| shop.Pricing#total | proved | Pricing.discount sha256:1ac7558b1eb3740fcf9b33b0cbe9820064479918fbc7ea97c7c758d585187ade |
| shop.Pricing#withQuantity | proved |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 48.7 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.2 |
| key's closures: both versions' closures digested | 1.2 |
| lookup: reading the store | 0.0 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 1350.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 35.2 |
| store: writing the result, a refutation's witness replayed first | 1.7 |
| replay of a stored or new witness (inside lookup and store) | 0.9 |
| outside every proof: compare's own steps after the last proof | 0.8 |

### defect, rerun (`offset`, from the cache the same build's run left)

5 proofs, 5 exact hits, 0 proved; in process 51.6 ms, as a process 106.6 ms (medians of 7)

| Subject | Reached | On the helper proofs |
|---|---|---|
| POST /quotes | exact hit |  |
| POST /quotes/text | unchecked |  |
| shop.Pricing#discount | exact hit |  |
| shop.Pricing#total | exact hit | Pricing.discount sha256:1ac7558b1eb3740fcf9b33b0cbe9820064479918fbc7ea97c7c758d585187ade |
| shop.Pricing#withQuantity | exact hit |  |
| shop.Money#cents | unchecked |  |
| shop.Quote#quantity | unchecked |  |

| Stage | ms |
|---|---|
| before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs | 47.2 |
| plan: both versions' reach and closures compared | 0.5 |
| key: the claim and its digest | 1.3 |
| key's closures: both versions' closures digested | 1.1 |
| lookup: reading the store | 0.2 |
| checker runs: decoding classes and methods (loading, lowering) | 0.0 |
| checker runs: exploring, encoding and solving | 0.0 |
| after the runs: the witness replayed, shrunk and run on a JVM, the statement | 0.0 |
| store: writing the result, a refutation's witness replayed first | 0.0 |
| replay of a stored or new witness (inside lookup and store) | 0.7 |
| outside every proof: compare's own steps after the last proof | 0.8 |
