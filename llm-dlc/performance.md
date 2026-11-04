# Where sync.py's time goes, and whether Go would help

The third changeset of the [sync speed brief](loops/sync-performance.md) ends with a measured
recommendation on a Go coordinator. This is it, measured on 2026-11-03 on the machine this repo
is developed on (8 ARM64 cores under WSL, 9 GB, Python 3.12.3, jj 0.46), with 20 sessions and 171
stored snapshots (476 MB gzipped). Run-time numbers come from `sync.py perf`; the rule-by-rule
numbers from [`tools/profile_rules.py`](tools/profile_rules.py), which prints rule names and
numbers only and can be run again.

**Decided (user, 2026-11-03): no Go port.** The recommendation it rests on:

**Recommendation: don't port to Go.** The common path is already short, and Go could shave about
2 s from it at most. The slow path is a cold scan after a rules change, and Python can fix it with
a cheap per-line gate and a process pool. Neither change touches the published format, so no
snapshot is put at risk. Go's two traps are real here: every published line would change bytes
under its default JSON encoder, and nine of the rules need lookaround. Revisit only under the
conditions [at the end](#when-to-look-again).

## The three paths

### A commit after a feature (the common path)

This is a small feature in this run's own session: 30 MB of log, of which about 0.6 M new
characters to redact. The caches are warm.

| Command | Wall | Main phases |
|---|---|---|
| `sync` (in commit) | 1.3 s | gzip of the new snapshot 0.30 s, redaction of the new lines 0.28 s, jj/git subprocesses 0.68 s CPU (13 calls), index 0.07 s |
| `check` (in commit) | 2.0 s | scan of the 2,033 new lines 0.77 s, metrics 0.28 s, SHA-256 of 171 `.gz` files 0.25 s, prefixes 0.15 s, trailers via jj/git 0.16 s |
| `sync`, nothing new | 0.18 s | index 0.08 s, 4 subprocesses |
| `check`, nothing new | 0.96 s | SHA-256 of the `.gz` files 0.25 s, trailers 0.17 s, prefixes 0.13 s |
| Stop hook, one turn | 0.5 s | from its cursor |
| Python start and imports | 0.06–0.08 s | of which `sync` imports 0.065 s |

Before this run, the same commit took 35–118 s. What remains has three parts:

- **External work.** jj and git calls cost 0.03–0.05 s each. Go would make the same calls.
- **Work already done in C.** zlib compression, SHA-256 (OpenSSL) and regex matching (`sre`) all
  run in C. Go's `compress/gzip` is not faster than zlib, and its SHA-256 uses the same CPU
  instructions.
- **Interpreted Python.** This is about 1–1.5 s across both commands, mostly the scan's per-string
  dispatch and the metrics.

Even if Go made all of that interpreted work free, a 3.3 s commit would still take about 1.2 s. It
saves about 2 s per feature, which does not justify a migration.

**Preparing in the background** while the agent works would save at most the redaction and gzip
in `sync`, about 0.6 s, and less than that once those overlap with jj. It is not worth a
persistent worker either.

### A cold scan (after a rules or redactor edit, `stamp`, or a new machine)

The first sync after the caches are emptied takes 70.6 s and the check 106.2 s. A full `scan`
takes 148 s.

Each step below re-profiles the largest log: 79 M characters, 29,745 lines and 1.5 million JSON
strings. Scanning it from cold takes 61 s. Parsing it takes 0.4 s and walking its strings
0.2 s; the rest is the rules:

```
  rule                             per string  one pass
  (a regex that never matches)          0.47s     0.05s
  personal literals (28)               11.11s     3.32s
  secret anthropic-key                  0.46s     0.05s
  secret langfuse-key                   0.69s     0.36s
  secret api-key                        1.47s     1.28s
  secret github-token                   1.54s     1.36s
  secret gitlab-token                   1.35s     1.29s
  secret aws-key                        1.35s     1.23s
  secret google-key                     1.26s     1.34s
  secret google-oauth                   1.30s     1.24s
  secret slack-token                    1.34s     1.29s
  secret slack-webhook                  0.54s     0.04s
  secret discord-webhook                0.49s     0.04s
  secret npm-token                      1.21s     1.39s
  secret huggingface-token              1.27s     1.34s
  secret stripe-key                     1.42s     1.36s
  secret sendgrid-key                   1.15s     1.33s
  secret jwt                            1.30s     1.50s
  secret private-key                    0.50s     0.03s
  secret bearer                         1.24s     1.32s
  secret basic-auth                     0.84s     0.57s
  secret url-password                   1.76s     1.72s
  secret curl-user                      1.67s     1.60s
  secret account-id                     0.74s     0.42s
  secret env-secret                     5.30s    15.00s
  email                                 2.41s     3.11s
  windows-user                          1.44s     1.52s
  username                              0.12s     2.74s
  review public-ip                      2.77s     2.64s
  review ipv6                           2.07s     1.83s
  review mac-address                    1.78s     1.91s
  review other-home-dir                 1.67s     1.38s
  review auth-header                    1.94s     2.02s
  review long-token                     2.44s     3.08s
  all rules                            57.94s    60.67s
```

The one-pass column applies no hints, which is why env-secret and the username rule cost more there.

Each rule has two costs. **Per string** is the cost as the scan applies the rule: once to each
of the 1.5 million strings, as `Rules.hits_of_line` does. **One pass** is the cost of a single
run over all the strings joined. Three findings follow from the two:

- **Personal literals are almost all call overhead.** There are 28 literal patterns (the home
  path, hostname, emails and account ids). Called once per string, they cost 11.1 s. In one
  pass, all 28 together take 3.3 s, most of it in the few case-insensitive ones. Even a regex that
  never matches costs 0.47 s when it is called per string, against 0.05 s in one pass. The cost is the 1.5 million
  calls from Python, not the matching.
- **Most credential rules cost about 1.3–1.7 s either way.** That is the matching itself:
  `sre` searches for a pattern that starts with `\b` or a character class at every position,
  at about 50 MB/s. Rules that start with a literal (`sk-ant-`, `https://hooks.slack.com`,
  `-----BEGIN`) take 0.05 s, because `sre` jumps to the literal. env-secret costs 5.3 s, or 15 s
  in one pass without its hint. The review rules cost 2–3 s each.
- **A per-line gate removes most of it.** One search per JSON line for any literal that a
  credential rule's match must contain takes 1.9 s. Only 3.3% of lines pass it (973 of 29,745).
  The other 97% would skip the 18 rules that have such a literal, which cost about 19 s on this
  log. The personal literals can be gated the same way, with one pass per line instead of one
  call per string. The gate has to be sound: it may skip a line only when the rule cannot match
  it. That means case folding as `re.I` does it, since `str.lower` does not fold ſ or the Kelvin
  sign. The existing `HINTS` mechanism and `stamp --equivalent` are the way to build and check it.

**The cold scan also parallelizes.** Lines are scanned independently, and the distinct lines of
the 20 sessions' latest logs (38,949 lines, 159 M characters) can be split into chunks:

| Processes | Wall | Summed CPU | Speed-up |
|---|---|---|---|
| 8 | 13.6 s | 98.7 s | 7.3× |
| 4 | 24.6 s | 95.4 s | 3.9× |

With both changes, the gate and a process pool, a cold scan of everything should drop from about
150 s to roughly 10–20 s. This was an estimate when written; measured with both in, below, a full
scan takes 11.6 s and a full check 18.0 s.

**The pool is in** (step 3e, `redactor.py`). Cold redaction and scanning go to one process per
CPU, which apply the same rules line by line. Measured on 2026-11-03 against the same state with
`LLM_TRACES_PROCESSES=1` (the code path from before), every cache bypassed with `--full`:

| Command | One process | 8 processes | Output |
|---|---|---|---|
| `check --full` | 112.1 s | 32.5 s (scan 20.0 s, of which the pool 15.0 s for 78.7 s of worker CPU; decompression 6.3 s) | identical |
| `scan --full` | 160.0 s | 32.0 s (redaction 11.9 s, scan 19.2 s) | identical |
| `sync --full` | 71.0 s | 17.9 s (redaction 11.7 s) | identical, 95–104 generated files unchanged |

The first `check --full` with the pool, which started it only for texts of 4 M characters or
more, took 43.8 s: most snapshots are scanned only past the end of an earlier one, and those
pieces stayed in one process. A started pool now takes any text of 250 k characters or more.

**The gate is in** (`GATES` in `redaction_rules.py`). Every rule has a gate: words that
every match holds (compared as `re.I` compares for the case-insensitive rules: by `str.lower`
only on all-ASCII text, where the two agree, else by the engine), an assertion-free pattern, or
both. It is tested once per line on the line's strings joined, and each rule also skips strings
shorter than its shortest match. On the largest log (79 M characters), measured on 2026-11-03,
CPU time in one process:

| Work | Before | With the gates | Output |
|---|---|---|---|
| scan (`hits_of_line` of each line) | 55.7 s | 14.1 s | identical |
| redaction (`Rules.__call__`) | 42.0 s | 14.2 s | identical |

Of the 13.4 s that remain in a scan, the gates take about 7 s: env-secret's hint on the 44% of
lines whose strings hold one of its words (2.6 s), the 28 personal literals (1.1 s), and the
class-led patterns of public-ip, ipv6, mac-address and long-token (about 0.5 s each). The rules
themselves take about 4.5 s, mostly env-secret (2.3 s) and long-token (1.5 s), whose gates pass
2.3% and 38% of lines. Parsing takes 0.55 s.

Whole commands, every cache bypassed with `--full`, against the step 3e numbers above (the state
has grown a little since: 20 sessions, 86,318 distinct lines):

| Command | 3e, 8 processes | Gates, 8 processes | 3e, one process | Gates, one process |
|---|---|---|---|---|
| `check --full` | 32.5 s | 18.0 s (20.1 s worker CPU, was 78.7 s) | 112.1 s | 37.8 s |
| `scan --full` | 32.0 s | 11.6 s | 160.0 s | not measured |

`check --full` printed the same in one process as in eight, and the same 0 errors and 13
warnings as before the gates. `stamp --equivalent` checked the gated rules against the stamped
ones on every distinct line of every transcript, log and published file: 86,318 lines, the same
results. It now also runs in one process per CPU, and took 92.9 s for 635 s of worker CPU, most
of it the old rules. In one process that would be about 10.5 minutes.

So the cold path is now under the 30 s at which [the conditions below](#when-to-look-again) said
to look again.

Go would remove the dispatch overhead, and goroutines would give the same parallelism. Its
standard `regexp` package, however, guarantees linear time with an NFA, a one-pass matcher and a
bounded backtracker. It has no DFA matcher like RE2's C++ one. So it is not expected to scan these
class-led patterns faster than `sre` does. This was not measured: there is no Go toolchain here,
and the brief keeps Go out of scope.

### A push

The upload stage was measured in step 3a against stubbed latencies: 0.15 s per CDN request plus
0.05 s per MB, and 2 s per wrangler put. It took about 45 s one log at a time and 26.5 s with
four logs in flight. With concurrent puts, it would take about 10 s. Those puts wait for the
user's decision on credentials (the R2 API token or concurrent wrangler logins, deferred in
step 3a).

The scan before the puts takes 0.04 s from check's caches. The stage waits on the network, not
on the CPU. Go would gain nothing here. An S3-compatible R2 client would gain a lot, and Python
can use one.

## What a port would have to keep

Two numbers make the brief's warnings concrete. Both were counted over the latest log of each
session: 50,535 lines.

- **JSON bytes.** Every one of the 50,513 lines that parse as JSON has its keys in insertion
  order, not sorted order. 36.7% of lines hold `<`, `>` or `&`, and 14.4% hold
  non-ASCII text that Python writes unescaped (`ensure_ascii=False`). Go's `encoding/json`
  sorts map keys and escapes HTML characters by default. A port that decodes into maps would
  therefore rewrite every line. That breaks every new snapshot's identity and its prefix
  relation to the snapshots already published. 22 lines are not JSON at all, and the redactor
  must keep handling them as text.
- **Lookaround.** Of the 36 rule patterns, 7 use lookahead or lookbehind: curl-user,
  env-secret, public-ip, ipv6, other-home-dir, long-token and the email rule. So do the hostname
  literals and the username pattern. Go's `regexp` has none. Each would have to be rewritten as
  code around a match, and proved to give the same result on every stored log.

## When to look again

Look at Go, or more likely at a native scanner, only if one of these holds:

- once the gate and the pool are in, a commit with warm caches still takes over about 5 s; or
- a cold scan of everything still takes over about 30 s; or
- something is needed that a short-lived Python process cannot give, such as a long-running
  preparation daemon that watches transcripts.

If it comes to that, port the scanner first, not the coordinator. Use an engine with a DFA and
multi-pattern matching (Rust's `regex` crate, RE2 in C++, or Hyperscan) rather than Go's
`regexp`. Leave serialization in Python, or check it byte for byte against every stored log, in
the differential tests the brief describes.
