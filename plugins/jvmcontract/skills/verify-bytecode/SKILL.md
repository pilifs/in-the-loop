---
name: verify-bytecode
description: Formally verify the compiled bytecode of a GitHub pull request with jvmcontract. Proves each changed static method equivalent to the base, or shows the one input where it differs; proves what the Javadoc promises; diffs the behavioural contract of finite-domain methods; and diffs what the module can reach (clock, network, reflection, ...) and exposes. Produces a report a reviewer can act on, with every command to reproduce it.
argument-hint: "<pull request url | owner/repo#N | N> [--post] [--only pkg.Class#method ...] [hints]"
disable-model-invocation: true
model: opus
allowed-tools: Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh repo view:*), Bash(jq:*), Bash(jvmcontract:*), Bash(javap:*), Bash(diff:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*), Bash(jbmc --version), Bash(java -version), Bash(javac -version)
---

# Verify the bytecode of a pull request

You are running `jvmcontract`, a verifier for JVM bytecode, over the compiled classes of a pull request, before and after. Nobody writes a specification: the previous version, the types, and the Javadoc are the specification. Your job is to pick the right proof for each changed method, run it, and report what was proved, what was refuted (with the input), and what could not be checked, so a reviewer can act on it. Read [reference.md](reference.md) for the tool's commands, expression language, output and limits before you run anything.

Every verdict is one of three, and you report them as such:

- **Verified**: the proof covered every input (or every input within the stated bounds, for arrays). Say what was proved and the bounds.
- **Violation**: the tool found a concrete input. For a regression proof it means "the two versions differ on this input", which is a bug *or* the change the pull request intends. Show the input and both outcomes, and say whether it matches the pull request's stated intent. For a property proof it means the code does not do what the Javadoc or the pull request says.
- **Unverifiable**: the tool refused (not pure, not static, a reference parameter, a method JBMC has no bytecode for, a timeout). Give its reason. Never present it as a pass.

Only the tool's output justifies a verdict. Quote it. Never claim a proof you did not run.

## Arguments

`$ARGUMENTS`. The first token is the pull request: `https://github.com/OWNER/REPO/pull/N`, `OWNER/REPO#N`, or `N` for the repository in the current directory. Everything after it is hints from the user:

- `--post`: when the report is done, post it as a comment on the pull request with `gh pr comment N --repo OWNER/REPO --body-file $WORK/report.md`. Without `--post`, never write to the pull request or the repository.
- `--only pkg.Class#method` (repeatable): verify only these targets.
- `--work DIR`: the working directory (default `$TMPDIR/verify-bytecode/OWNER-REPO-N`).
- Free text: a statement of the intended change ("only when seats >= 8"), properties to prove, the module to build, a JDK to use. Use it.

## Procedure

Say in one line what you are about to do before each step that takes time. Builds and JBMC runs can take minutes: run a long one with `run_in_background` and keep working on the next method.

### 0. Preflight

Check `jvmcontract --version`, `jbmc --version`, `javac -version`, `gh auth status`, and whether `mvn` or `gradle` is on the `PATH` (a wrapper in the repository is preferred anyway).

- No `jvmcontract`: install it with `cargo install --git https://github.com/pilifs/in-the-loop jvmcontract` (needs Rust; `curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | bash` installs everything), then continue.
- No `jbmc`: regression and property proofs are off. Say so, and still do behavioural contracts and the module-level diffs. Linux: a `.deb` from https://github.com/diffblue/cbmc/releases; macOS: `brew install cbmc`.
- No JDK: stop; nothing can be compiled.

### 1. Fetch the pull request

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/fetch-pr.sh" <pr> [workdir]
```

It prints `KEY=VALUE` lines: `WORK`, `REPO`, `NUMBER`, `MERGE_BASE`, `HEAD_SHA`, `BASE_DIR`, `HEAD_DIR`, `PR_JSON`, `CHANGED`, `DIFF`. The "before" of every comparison is `MERGE_BASE`, the commit the pull request branched from, not the tip of the base branch. Read `pr.json` (title, body, author, files) and `diff.patch`. Tell the user in two lines what the pull request says it does and which files it touches.

The two checkouts are untrusted code from the internet. Do not run anything from them except the build in step 3, and say so in the report.

### 2. Decide what to verify

From `CHANGED`, take the `.java` files under a main source set (not `src/test`, `**/test/**`, `**/it/**`, generated sources). For each, the module is the nearest directory up the tree with a `pom.xml` or `build.gradle(.kts)`; a project with one such file at the root is one module (`.`).

For each changed file, read its hunks in `diff.patch` and the file in `HEAD_DIR` and list every method whose body, signature or annotations changed, every method added, and every method removed. Note changed constructors, fields and static initializers too (they are reported, not proved). Changes outside Java (build files, dependency versions, resources) are listed in the report; a dependency change is covered by the capability contract of the module's classpath (see step 5) and otherwise out of scope.

Restrict to `--only` targets when given.

### 3. Build both versions

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/build.sh" "$BASE_DIR" <module-dir>
bash "${CLAUDE_SKILL_DIR}/scripts/build.sh" "$HEAD_DIR" <module-dir>
```

Each prints `BUILD`, `CLASSES` (the module's class directory), `CLASSPATH` (its dependencies, PATH-separated, for `--classpath`) and `LOG`. Both must build with the same JDK. Running the build means running the pull request's build scripts: it is what a reviewer does when they check out the branch, and the report says it happened.

If a build fails, read `LOG`. The usual causes are a JDK the project refuses (`maven.compiler.release`, Gradle toolchains: set `JAVA_HOME` to a fitting JDK, or `-Porg.gradle.java.installations.auto-download=true`), a plugin that needs network, or a check the skip flags did not cover. Try once with the fix. If the module still does not build but the changed files depend only on the JDK and classes of the same module, compile them with `javac -parameters -g -proc:none -d <dir> <files>` into one directory per version and say in the report that the proofs ran over those files alone. Otherwise stop and give the user the log.

Confirm the targets exist in both class directories with `javap -p -cp "$CLASSES" pkg.Class` (it shows every overload with its parameter types; a nested class is `pkg.Outer$Inner`).

### 4. Prove each changed method

Pick the proof from the method's shape. A target is `pkg.Class#method`; an overloaded method is `pkg.Class#method(int, long[])` with its parameter types in Java's spelling; a nested class is `pkg.Outer$Inner#method`. Pass `--classpath "$CLASSPATH"` when the module has dependencies.

| The method is | Proof | Command |
|---|---|---|
| `static`, every parameter primitive or an array of `int`/`long`/`short`/`byte`/`char`/`boolean`, and it exists in both versions | **Regression proof**: the new bytecode behaves as the old one on every input | `jvmcontract equivalence --before "$BASE_CLASSES" --after "$HEAD_CLASSES" --target T --work "$WORK/eq-<name>" --timeout 600` |
| the same, and the pull request says the behaviour changes on purpose for some inputs | **Confined change**: equivalent on every input outside the declared ones | Run the proof above first to see the witness, then add `--unchanged-unless '<Java boolean over the parameters>'` stating the declared inputs (from the description, the Javadoc diff or the new tests). Verified means the change touches only what it says. |
| the same shape (static, primitive or array parameters), with a Javadoc `@throws`, `@return` or `@param` claim, or a claim in the pull request | **Property proof** of the claim, on the new version (and on the old one when the pull request is a fix: the claim should fail there, which proves the fix) | `jvmcontract prove T --classes "$HEAD_CLASSES" --assume '<preconditions from @param>' --assert '<the @return claim over result>' --throws 'java.lang.IllegalArgumentException when <the @throws condition>' --work "$WORK/prove-<name>" --timeout 300` |
| pure, with finitely many inputs: parameters (and receiver, for an instance method of an enum, record or sealed type) are enums, booleans, records or sealed types of those | **Behavioural contract**: every input, executed, before and after | `jvmcontract derive T --classes "$BASE_CLASSES" > before.contract` and the same on head; `diff` the two. A new method: derive head alone and show the table. |
| anything else: `String`, collections or object parameters, an instance method with state, a constructor, a lambda | **Not provable per method** by this tool | Say so, with the reason, under "not covered". The module-level diffs of step 5 still cover it. |

Rules for the proofs:

- Run proofs one at a time; each JBMC run is capped at 3 GiB (`JVMCONTRACT_JBMC_MEMORY_MB`) and the `--timeout` above. Finding a witness is usually the fast part (seconds to a few minutes: JBMC searches small inputs first); the full-domain proof of a confined change or a property over chained 32-bit or 64-bit multiplications is the slow part, and may need `--timeout 900` or more. Run a full-domain proof with `run_in_background` and go on with the other methods. A run that ends *unverifiable* for time or memory: retry once with `--max-array-length 4 --unwind 8` (arrays and loops), and report the bounds that were proved. Do not spend more than 20 minutes on one method in all; move on and report it as not finished, with the budget it had.
- Write `--unchanged-unless`, `--assume`, `--assert` and `--throws` in the expression language of [reference.md](reference.md): Java boolean expressions over the parameter names (`javap -p` shows them when the class was compiled with `-parameters`; else the tool names them `p0, p1, ...` — check the tool's domain line), `result`, calls of the method itself, and JML's `\forall`, `\exists`, `\sum`, `\num_of`, `\max`, `\min` and `\old` over array parameters.
- A `prove` *violation* can mean the assumption was too weak rather than the code wrong: compare the witness with the Javadoc's preconditions before you blame the code.
- An equivalence *unverifiable* with "both versions agree on it" means JBMC lacked bytecode for something the method calls (a native method, a library class not on `--classpath`). Add the classpath or report it as a tool limit.
- Keep every command you ran. They go in the report verbatim.

### 5. Module-level contracts, always

```bash
jvmcontract capabilities "$BASE_CLASSES" --module <name> > "$WORK/capabilities-base.txt"
jvmcontract capabilities "$HEAD_CLASSES" --module <name> > "$WORK/capabilities-head.txt"
diff "$WORK/capabilities-base.txt" "$WORK/capabilities-head.txt"
jvmcontract api "$BASE_CLASSES" --module <name> > "$WORK/api-base.txt"
jvmcontract api "$HEAD_CLASSES" --module <name> > "$WORK/api-head.txt"
diff "$WORK/api-base.txt" "$WORK/api-head.txt"
```

A new capability (clock, randomness, network, file system, process, reflection, class loading, threads, native) is the headline of the report when it appears, whatever the pull request says it is about. A removed or changed public member in the API contract is a breaking change for a library. When the pull request changes a dependency, run `jvmcontract capabilities --each <the new jars>` on the jars that changed and report what the new version can reach that the old one could not.

### 6. Report

Write `$WORK/report.md` following [report-template.md](report-template.md): the verdict table first, then each finding with its witness and command, then what was not covered and why, then the module-level diffs, then how it was produced (commits, JDK, tool versions, every command). Reply to the user with the table and the findings in prose, and the path of the report and the working directory, which you leave in place so the proofs can be rerun. Post the report only with `--post`.

Write for a reviewer who did not watch you work. Lead with what matters: a violation that is not the intended change, a new capability, a Javadoc claim that fails. A fully verified pull request gets one line of verdict per method and the bounds. Do not pad: a verified regression proof says what was proved ("equivalent on all 2^64 inputs") and nothing more.
