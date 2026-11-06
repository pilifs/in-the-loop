# The solver comparison, word-level

`lib/solvers/compare.py` at `?` on claude-vm (x86_64, AMD RYZEN AI MAX+ 395 w/ Radeon 8060S, 28 CPUs), 2026-11-06T23:14:23+0000: jvmcontract 0.1.0, openjdk version "25.0.5" 2026-10-20 LTS. Each case under strict, unwind 16, arrays up to 8, 3 runs of each check and replay; seconds are the median, with the range in brackets.

The solvers, as the checks' statements name them:

- Bitwuzla 0.8.2 (the engine's terms: word-level operations as bit-vector terms, gates as Boolean terms; sat-solver cadical, produce-models, otherwise defaults)
- Bitwuzla 0.8.2 (the engine's terms: word-level operations as bit-vector terms, gates as Boolean terms; sat-solver cadical, produce-models, preprocess=0, otherwise defaults)
- CaDiCaL 1.9.5 (bundled)

Bitwuzla's library: `/home/filip/tools/bitwuzla/bitwuzla-0.8.2/lib/x86_64-linux-gnu/libbitwuzla.so.0`, sha256 `eac09e6d6f892ae0…`.

CaDiCaL is given the engine's clauses; `bitwuzla-words` its gates as Boolean terms and its word-level operations as bit-vector terms, so its clause count is only the constant's unit clause, and *Word ops* counts the operations it was given as terms.

## Full checks

| Case | Solver | Verdict | Seconds | Solver calls | Clauses | Word ops | Solving (engine) | Peak MB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| real/midpoint/search-within-bound | cadical | verified | 1.736 (1.736–1.805) | 942 | 240144 | – | 1.583 (1.582–1.637) | 70 |
| real/midpoint/search-within-bound | bitwuzla-words | verified | 1.469 (1.463–1.472) | 937 | 1 | 626 | 1.352 (1.351–1.355) | 77 |
| real/midpoint/search-within-bound | bitwuzla-words:preprocess=0 | verified | 0.900 (0.899–0.912) | 937 | 1 | 626 | 0.793 (0.787–0.800) | 68 |
| example/141 | cadical | verified | 1.316 (1.305–1.330) | 1044 | 137013 | – | 1.183 (1.174–1.188) | 58 |
| example/141 | bitwuzla-words | verified | 2.037 (2.036–2.057) | 1124 | 1 | 694 | 1.904 (1.900–1.924) | 76 |
| example/141 | bitwuzla-words:preprocess=0 | verified | 1.279 (1.269–1.290) | 1124 | 1 | 694 | 1.142 (1.142–1.155) | 77 |
| example/142 | cadical | verified | 4.696 (4.630–4.745) | 1885 | 161165 | – | 4.513 (4.443–4.563) | 82 |
| example/142 | bitwuzla-words | verified | 10.086 (9.996–10.089) | 1891 | 1 | 3633 | 9.693 (9.609–9.693) | 216 |
| example/142 | bitwuzla-words:preprocess=0 | verified | 3.594 (3.559–3.603) | 1894 | 1 | 3633 | 3.288 (3.284–3.308) | 89 |
| held/reverse | cadical | verified | 0.153 (0.152–0.153) | 115 | 59707 | – | 0.086 (0.085–0.088) | 39 |
| held/reverse | bitwuzla-words | verified | 0.112 | 125 | 1 | 331 | 0.051 (0.050–0.051) | 43 |
| held/reverse | bitwuzla-words:preprocess=0 | verified | 0.092 (0.091–0.092) | 125 | 1 | 331 | 0.033 | 44 |
| held/prefix-sums | cadical | verified | 0.051 | 18 | 5637 | – | 0.000 (0.000–0.001) | 31 |
| held/prefix-sums | bitwuzla-words | verified | 0.061 (0.051–0.061) | 19 | 1 | 25 | 0.004 | 35 |
| held/prefix-sums | bitwuzla-words:preprocess=0 | verified | 0.051 | 19 | 1 | 25 | 0.001 | 35 |

## Problems

None: every decisive verdict is the expected one, CaDiCaL's on every case.

## Not decided

Nothing: every check gave a verdict.
