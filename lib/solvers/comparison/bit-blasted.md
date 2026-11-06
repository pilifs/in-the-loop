# The solver comparison, bit-blasted

`lib/solvers/compare.py` at `?` on claude-vm (x86_64, AMD RYZEN AI MAX+ 395 w/ Radeon 8060S, 28 CPUs), 2026-11-06T23:10:16+0000: jvmcontract 0.1.0, openjdk version "25.0.5" 2026-10-20 LTS. Each case under strict, unwind 16, arrays up to 8, 3 runs of each check and replay; seconds are the median, with the range in brackets.

The solvers, as the checks' statements name them:

- Bitwuzla 0.8.2 (the engine's clauses as Boolean terms; sat-solver cadical, produce-models, otherwise defaults)
- Bitwuzla 0.8.2 (the engine's clauses as Boolean terms; sat-solver cadical, produce-models, preprocess=0, otherwise defaults)
- CaDiCaL 1.9.5 (bundled)

Bitwuzla's library: `/home/filip/tools/bitwuzla/bitwuzla-0.8.2/lib/x86_64-linux-gnu/libbitwuzla.so.0`, sha256 `eac09e6d6f892ae0…`.

## Full checks

| Case | Solver | Verdict | Seconds | Solver calls | Clauses | Solving (engine) | Peak MB |
|---|---|---|---:|---:|---:|---:|---:|
| real/midpoint/search-within-bound | cadical | verified | 1.747 (1.736–1.755) | 942 | 240144 | 1.581 (1.574–1.600) | 71 |
| real/midpoint/search-within-bound | bitwuzla | verified | 27.658 (25.011–34.543) | 942 | 240144 | 25.217 (22.645–31.954) | 596 |
| real/midpoint/search-within-bound | bitwuzla:preprocess=0 | verified | 25.230 (20.952–66.971) | 943 | 240144 | 22.872 (18.407–63.973) | 547 |
| example/141 | cadical | verified | 1.436 (1.375–1.495) | 1044 | 137013 | 1.259 (1.211–1.327) | 59 |
| example/141 | bitwuzla | verified | 61.600 (61.540–69.262) | 1044 | 137013 | 60.064 (59.978–67.676) | 399 |
| example/141 | bitwuzla:preprocess=0 | verified | 7.373 (7.262–7.618) | 1044 | 137013 | 5.998 (5.921–6.271) | 345 |
| example/142 | cadical | verified | 4.888 (4.824–5.041) | 1885 | 161165 | 4.698 (4.636–4.841) | 84 |
| example/142 | bitwuzla | verified | 41.236 (40.940–45.775) | 1888 | 161165 | 39.325 (39.057–43.824) | 567 |
| example/142 | bitwuzla:preprocess=0 | verified | 18.482 (18.159–18.963) | 1892 | 161165 | 16.647 (16.376–17.170) | 469 |
| held/reverse | cadical | verified | 0.152 | 115 | 59707 | 0.084 (0.083–0.086) | 39 |
| held/reverse | bitwuzla | verified | 3.855 (3.692–4.039) | 115 | 59707 | 3.389 (3.227–3.569) | 211 |
| held/reverse | bitwuzla:preprocess=0 | verified | 1.503 (1.432–1.523) | 115 | 59707 | 1.081 (1.015–1.082) | 182 |
| held/prefix-sums | cadical | verified | 0.061 (0.051–0.061) | 18 | 5637 | 0.000 (0.000–0.001) | 31 |
| held/prefix-sums | bitwuzla | verified | 0.122 | 18 | 5637 | 0.051 | 49 |
| held/prefix-sums | bitwuzla:preprocess=0 | verified | 0.101 (0.101–0.112) | 18 | 5637 | 0.038 (0.038–0.039) | 47 |

## CaDiCaL's transcripts replayed

The same calls on every solver. *Whole* is the replay's own time: reading the transcript, adding the clauses and every call; *solving* is the time inside the calls.

| Case | Transcript | Calls | Clauses | Solver | Whole s | Solving s | Contradictions |
|---|---|---:|---:|---|---:|---:|---:|
| real/midpoint/search-within-bound | 1311586-1.icnf | 942 | 240144 | cadical | 2.219 (2.066–2.227) | 2.145 (1.998–2.154) | 0 |
| real/midpoint/search-within-bound | 1311586-1.icnf | 942 | 240144 | bitwuzla | 32.981 (31.486–40.835) | 32.301 (30.775–40.121) | 0 |
| real/midpoint/search-within-bound | 1311586-1.icnf | 942 | 240144 | bitwuzla:preprocess=0 | 14.687 (12.950–14.724) | 14.033 (12.319–14.049) | 0 |
| example/141 | 1341287-1.icnf | 1044 | 137013 | cadical | 1.270 (1.248–1.273) | 1.238 (1.216–1.240) | 0 |
| example/141 | 1341287-1.icnf | 1044 | 137013 | bitwuzla | 60.309 (58.962–60.546) | 59.940 (58.591–60.174) | 0 |
| example/141 | 1341287-1.icnf | 1044 | 137013 | bitwuzla:preprocess=0 | 5.932 (5.791–6.077) | 5.556 (5.424–5.703) | 0 |
| example/141 | 1341287-2.icnf | 5 | 3037 | cadical | 0.001 | 0.000 | 0 |
| example/141 | 1341287-2.icnf | 5 | 3037 | bitwuzla | 0.033 (0.032–0.034) | 0.031 (0.030–0.032) | 0 |
| example/141 | 1341287-2.icnf | 5 | 3037 | bitwuzla:preprocess=0 | 0.025 (0.024–0.026) | 0.023 (0.021–0.023) | 0 |
| example/142 | 1375850-1.icnf | 1885 | 161165 | cadical | 5.033 (4.688–5.043) | 4.993 (4.649–5.005) | 0 |
| example/142 | 1375850-1.icnf | 1885 | 161165 | bitwuzla | 42.101 (39.202–44.022) | 41.607 (38.745–43.559) | 0 |
| example/142 | 1375850-1.icnf | 1885 | 161165 | bitwuzla:preprocess=0 | 15.918 (15.245–16.181) | 15.430 (14.774–15.682) | 0 |
| held/reverse | 1338098-1.icnf | 115 | 59707 | cadical | 0.097 (0.096–0.118) | 0.084 (0.083–0.100) | 0 |
| held/reverse | 1338098-1.icnf | 115 | 59707 | bitwuzla | 4.082 (3.977–4.159) | 3.955 (3.853–4.034) | 0 |
| held/reverse | 1338098-1.icnf | 115 | 59707 | bitwuzla:preprocess=0 | 1.538 (1.513–1.546) | 1.393 (1.371–1.405) | 0 |
| held/prefix-sums | 1341259-1.icnf | 18 | 5637 | cadical | 0.002 (0.002–0.003) | 0.000 (0.000–0.001) | 0 |
| held/prefix-sums | 1341259-1.icnf | 18 | 5637 | bitwuzla | 0.058 (0.055–0.058) | 0.053 (0.051–0.053) | 0 |
| held/prefix-sums | 1341259-1.icnf | 18 | 5637 | bitwuzla:preprocess=0 | 0.042 | 0.037 (0.037–0.038) | 0 |

## Problems

None: every decisive verdict is the expected one, CaDiCaL's on every case, and every replay agrees with its recording.

## Not decided

- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla (run 1): 4 of 942 calls stopped at their recorded limit
- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla (run 2): 7 of 942 calls stopped at their recorded limit
- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla (run 3): 2 of 942 calls stopped at their recorded limit
- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla:preprocess=0 (run 1): 3 of 942 calls stopped at their recorded limit
- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla:preprocess=0 (run 2): 3 of 942 calls stopped at their recorded limit
- real/midpoint/search-within-bound 1311586-1.icnf on bitwuzla:preprocess=0 (run 3): 2 of 942 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla (run 1): 6 of 1885 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla (run 2): 5 of 1885 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla (run 3): 5 of 1885 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla:preprocess=0 (run 1): 1 of 1885 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla:preprocess=0 (run 2): 2 of 1885 calls stopped at their recorded limit
- example/142 1375850-1.icnf on bitwuzla:preprocess=0 (run 3): 1 of 1885 calls stopped at their recorded limit
