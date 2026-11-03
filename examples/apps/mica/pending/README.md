# Pending: the regression proof of `ModifiedUtf8#encodeInto`

**Status: proved only up to 4 characters. The proof at the default bounds is waiting for a machine with more memory.**

This is a proof that has not been done, not a result. It isn't one of the numbered examples, and nothing here changes the committed code. The properties of `encodeInto` in [`properties.contract`](../src/contract/properties.contract), and examples [044](../../../044-modified-utf8-with-a-one-byte-nul/README.md), [048](../../../048-constant-pool-encoder-that-writes-supplementary-characters-in-four-bytes/README.md) and [055](../../../055-encoder-that-zero-terminates-into-the-callers-buffer/README.md), are a different statement and are proved.

## What it is for

Two planned examples add an ASCII fast path to `encodeInto`:

| Planned example | Patch | The change | Expected verdict |
|---|---|---|---|
| 057 | [`ascii-fast-path.patch`](ascii-fast-path.patch) | The test is `(char) (c - 1) < 0x7f`, which is U+0001 to U+007F | Proved equal to the previous version, with no property written |
| 058 | [`ascii-fast-path-that-admits-u0080.patch`](ascii-fast-path-that-admits-u0080.patch) | The test is `<= 0x7f`, which also admits U+0080 and writes it as the single byte `0x80` | Refuted. The committed properties don't catch it: only comparing with the previous version does |

## What has been measured

On a 10 GB WSL machine, with JBMC 6.11.0, JBMC limited to 3 GiB, and the other services left running:

| Patch | `--max-array-length` | `--unwind` | Result | Peak memory | Time |
|---|---|---|---|---|---|
| 058 | 2 | 6 | **Refuted**, on U+0080 | 570 MB | 6 s |
| 058 | 4 | 8 | **Refuted** | 1.5 GB | 38 s |
| 057 | 2 | 6 | **Proved** | 575 MB | 31 s |
| 057 | 3 | 6 | **Proved** | 600 MB | 94 s |
| 057 | 4 | 6 | **Proved** | 664 MB | 275 s |
| 057, 058 | 8 | 10 | No verdict: out of memory | Over 2.8 GB | 15 s |
| 057 | 8 | 16 (the defaults) | No verdict: out of memory | Over 2.8 GB | 15 s |

So the bug in 058 is found on this machine, and 057 is proved at small bounds. What's missing is 057, and a run of 058, at the default of 8.

## What a bounded proof doesn't say

The bound applies to `chars` and to `out` alike. At length 4, `out` holds at most 4 bytes, so an input that encodes to more overflows the buffer in both versions and is compared only up to that exception. Four three-byte characters need 12 bytes, so they are never encoded to the end. A difference that needs a longer encoding wouldn't be seen, which is why the proof at 8 is still worth having.

## How to pick it up

A build of `jvmcontract`, `javac` and `jbmc` are needed. Run the proof at the defaults with a higher limit:

```bash
export JVMCONTRACT_JBMC_MEMORY_MB=16384
examples/apps/mica/pending/prove.sh examples/apps/mica/pending/ascii-fast-path.patch
examples/apps/mica/pending/prove.sh examples/apps/mica/pending/ascii-fast-path-that-admits-u0080.patch
```

The memory it needs is unknown. Before the limit existed, the run reached 5.7 GB without finishing, so 16 GB is a guess. Memory may not be the only obstacle: at lengths 3 and 4 the time grew faster than the memory, so `prove.sh` allows an hour per JBMC run, and `TIMEOUT` changes that.

If both give the expected verdict, make them examples 057 and 058 as [`examples/README.md`](../../../README.md#run-an-example) describes, and delete this directory.

Don't add `--no-refine-strings` to save memory. JBMC ran out of memory with it too, even at 5 GiB, and adding it through a wrapper only appeared to finish, which was a parser bug that has since been fixed.

If no larger machine is available, 057 and 058 can be published at the bounds above, stating them, as the examples of a bounded proof they are.
