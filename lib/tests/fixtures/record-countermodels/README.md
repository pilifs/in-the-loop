# Countermodels of a call's record

The challenge stream of `domain-advances` (2026-11-18), item 5. It targets the preservation stream's call-level rule
as `mwvyxxyr` leaves it, at `lxosnzun` (preservation's merge of the default line, which holds `mwvyxxyr`).

The rule (`lib/src/bmc/ties.rs`) records each call it takes as one function of both versions (`ties::Call`): its
inputs as bits, whether it threw, the cells it wrote, and its result. An array result is named by the object's
number. A later call of the same code on equal inputs takes the earlier call's outcome. For an array result, that is
the cells of the object the record names, read when the later call is made (`path.objects[*t].array.cells`).
`mwvyxxyr` makes the record follow `collect`'s renumbering, and drops a result the state no longer reaches.

What the record leaves out, each shown by a pair below:
- **What the caller did to the result.** The record names the object, not the cells it was returned with. A caller
  that writes into the first call's array changes what the second call returns. This is older than `mwvyxxyr`: the
  reuse reads the object's cells in `xuwlklyo` too.
- **Which object it is on the other path of a merge.** `absorb` keeps the records of the path it merges into, with
  that path's numbers. `same_shape` merges two paths object by object, by number, and `collect` numbers each path's
  objects in the order its state reaches them. So where one path reaches the result first and the other path reaches
  another array first, the merged record names the result on one path only. On the other path it names the other
  array. `renumber`, which `mwvyxxyr` extends, renumbers one path's records. Nothing compares the two paths' records.

`Shared.make(k)` returns a new `int[1]` holding k. It compiles to the same bytes in `old/` and `new/` (the JVM test
checks it), and it has a loop of three rounds, since the rule takes no call of loop-free code. `Entry` differs.

| Method | Previous alone | New alone | What differs | Why the rule does not see it |
|---|---|---|---|---|
| `stale` | 0 at 0 | 99 | the previous version writes 99 into the first call's array and returns the second call's cell; the new one returns 99 | the second call is related to the first and takes the cells the first's array holds now, 99 |
| `swapped` | 3 at 1 | 2 | the first call's array goes to `a` on an even k and to `b` on an odd one, with a new `int[1]` in the other local | at the join the two paths number the result differently, and the merged record names the new array on one of them |

Each version's `main` runs both methods alone (`lib/tests/record_countermodels.rs`,
`each_version_alone_differs_past_the_second_call_on_a_jvm`).

On the checker at `lxosnzun`, built apart with the sources touched, `--engine native --assume 'k >= 0'`:
- `stale` is **Verified**: "the two versions agree on every input where k >= 0", non-vacuous (`agree(k=20) reaches
  the calls`), with "13 calls of methods both versions share taken as one function of both, 12 of them related".
  Nothing is stated but the rule's own assumption that each call ends, and each call here ends. It is the same with
  `--no-shared-callees`.
- `swapped` has **no verdict**: a spurious witness (`agree(k=16)`), which the interpreter does not reproduce. It
  explored 973 paths with 398 merges. Its new version's mirror, with the parities exchanged, gives a spurious witness
  at `k=0`. So the merged record names the wrong array on even k in one group of paths, and on odd k in another,
  depending on which path the merge keeps. A wrong value is reproduced. This is not a false proof, because the
  callee's result is an uninterpreted function of its inputs, and the new version cannot match a value that depends
  on which path was kept. Each version takes 30 independent branches first, because the checker merges paths only
  once it has explored 512 (`merge_after`) and renumbers heaps only past 1024 (`merge_heaps_after`). With 11, it
  explored 726 paths, renumbered nothing and refuted the pair, as it should.

The checker is right without the rule. On this line's checker, which has no call-level rule, the call runs as
written.

## The commands

With the fixtures compiled into `old/` and `new/` (`javac -g -parameters --release 21`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#stale' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0'
```

The same for `swapped`.

## What the checker should say instead

This is the preservation stream's to decide, since the rule is its own this run. Options:

- **Cells**: record an array result's cells as bits when the call returns, as `written` is recorded, and have a later
  call take those. Alternatively, drop the record's result once anything stores into the object.
- **Merges**: in `absorb`, keep a record's result only where both paths name the same object by it, after `align`'s
  renumbering. Elsewhere, drop it or make it a `Val::C` choice by the absorbed path's condition.

The test the checker would pass after the fix, to be added to `lib/tests/record_countermodels.rs` with it. At
`lxosnzun` it fails on `stale`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone tells both methods apart (the test above), so a proof that they agree is
/// false.
#[test]
fn a_calls_record_does_not_prove_what_its_result_held_before() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["stale", "swapped"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("record-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though each version alone tells them apart: {wrong:?}");
}
```

## Audit

- **287's preservation**, accepted at bound 80: in both pinned sources JARs (6.3.7 and 6.3.8, sha256s as in 287's
  `sources.lock.json`), `hashpw(byte[], String, boolean)` makes one `crypt_raw` call per call of its own and passes the
  result only to `encode_base64`, which reads it and stores nothing into it. No caller writes into a result before a
  later call. So `stale` cannot occur there.
- **307's two tasks**: their route's slices were not reread for this.
- **Merges**: a record's result is read only by a later call that is related to it. Whether a merge falls between two
  related `crypt_raw` calls in 287's or 307's harness was not read. That is an open point for the fix, not a
  finding.
- **289 and 290**: whether their reruns take a call was not read, which the function-countermodels audit also leaves
  open.

Nothing for the watcher. No accepted result is shown to rest on either hole.
