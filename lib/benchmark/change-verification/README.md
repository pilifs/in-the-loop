# Verifying one application change

`examples/tools/build.py --change-plan` inventories caller operations on both application deployments and records a separate obligation for each declared observation. The plan records the ordered classpaths, JDK image identity, selected caller methods, unresolved framework obligations, original-entry trials, assumptions and receipts. [Implementation](../../../examples/tools/targets/change_plan.py)

For a numbered example, the command reads the existing target and qualifies its receipts. An ordinary attempt that timed out remains visible alongside a completed native partition or finite JVM result. The Guava examples also identify the precise method or solver query checked independently.

```sh
python3 examples/tools/build.py --change-plan example 345 --output "$TMPDIR/importer-plan.json"
```

For an application, supply the two prepared manifests and a workflow file. Each manifest identifies its first client JAR and every subsequent runtime provider in classpath order with a `file` and `sha256`. It also carries the preparation's `commit` and `sourceSha256`. Relative artifact paths resolve against their manifest. Optional `environmentFiles` bind external files by path and digest. Optional test manifests are inventoried separately with `--before-test` and `--after-test`. A different new runtime uses `--after-jdk`.

```sh
python3 examples/tools/build.py --change-plan application \
  --before old/prepared.json --after new/prepared.json --jdk "$JAVA_HOME" \
  --workflows workflows.json --fixtures original-fixtures \
  --run --cache "$TMPDIR/change-proofs" --output change/first.json
```

Omitting `--run` produces the inventory and frozen obligations. `--previous change/first.json` adds the per-claim delta to the next report. For a library upgrade, `--old-dependency` and `--new-dependency` identify the selected JAR digests. For a client refactor the runner tracks the client itself. When the client bytes differ, it also tries the old client on the new provider graph, with separate results for that binary-compatibility question.

Each workflow names a finite observation specification, an original-entry Java observer, its cohort, and its intended behavior. Use `preserve`, `undecided`, or `{"allowedChanges":[{"input":0,"expectedNew":{"return":"new value"}}]}`. The last form changes the expectation only for the named input. The Wire fixture contains one historically registered direction and one later discovery. Both construct the converters through the public Retrofit factory. [Workflow file](wire-workflows.json)

The JVM must reach the selected invocation twice on each input and load the tracked provider. An escaping exception also needs two matching call frames on the original client. One witnessed difference can refute the finite preservation claim. Establishment requires coverage of every declared input and a closed deterministic environment under the listed assumptions. Earlier startup failures keep their own evidence. Cache entries bind the full ordered runtime, JDK, compiled observer, fixture and checker identities and proof settings. The runner replays divergent outcomes when resuming. An unresolved initializer, a matching gap description or a single captured receiver never establishes a caller.

The evaluations can be repeated from the setup recorded in the brief.

| Command from the repository root | Evidence |
|---|---|
| `python3 lib/benchmark/change-verification/importer.py --output "$TMPDIR/importer.json"` | All four original deployments, finite decisions and controls, dependency interactions, order changes, and fresh checks of composed results. |
| `python3 lib/benchmark/change-verification/wire_matrix.py --baseline-only --output "$TMPDIR/wire/summary.json"` | Independently discovered converters and their historical outcomes, graded after running the public callers. The whole six-configuration matrix runs as a verification job. |
| `python3 lib/benchmark/change-verification/portfolio.py --check --output verification/change-verification/portfolio.json` | Recheck the receipt bindings of the semantics and receiver retries, Spring blockers and independent Guava nodes. |
| `python3 lib/benchmark/organic-java/report.py --check` | Recount the published campaign on its pinned inputs. Use `--current --output PATH` to include subsequent receipts. |

The held-back application uses three pre-registered workflows on one deployment JDK. Its measurement records binary compatibility, unchanged-source compilation, and the upstream adapted application separately. The full cost comparison starts a fresh verifier process for each pass and includes source preparation, Maven resolution and compilation. [Registration](petclinic.json) · [Evaluation results](../../../llm-dlc/loops/in-the-loop-change-verification-strategy-results.md)
