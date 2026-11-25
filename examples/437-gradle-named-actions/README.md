# Gradle fingerprints a named Groovy task action across incremental builds

Editing A to B left the named action up to date on the parent method. The merged method reran both action forms, and the incremental doFirst output matched a fresh B build. Both unchanged controls skipped correctly.

Both sides run on one verified Gradle 7.6 distribution. The registered named-action method is compiled from each exact pin. The setup replaces this one method in the released AbstractTask class. A build init script checks the executing class bytes on every invocation. Each revision's original verification policy accepted all three archived build dependencies. A separate job builds both complete distributions.

| Question | Input |
|---|---|
| Intent | Run A then B with the same action name, task path, declared output and local execution history. |
| Control | Immediately repeat the successful A build with exactly the same script, output file and settings. |
| Challenge | Use a single named doFirst action in an otherwise identical task. Compare the B output of the incremental A→B history against B built directly in an empty project with the same B script. |

Run `python3 examples/tools/build.py 437` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pinned-method-on-7.6. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/gradle/gradle/pull/21084) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

Prepare the two derived JARs with `python3 examples/437-gradle-named-actions/setup/prepare.py` before replay on a fresh setup. This verifies the published distribution, reads both source files directly from each Git pin, compiles them and transplants the named-action method onto Gradle 7.6. [Build recipe](setup/prepare.py) · [Expected derived JARs](setup/artifacts.sha256)

The first full build accepted grolifant and stopped while configuring the documentation project's plugin classpath. HTTP Builder 0.11.1 was missing from the Plugin Portal. A public JCenter mirror supplied its original JAR, POM and both detached signatures. The signatures were made in December 2016 by the key trusted by each Gradle revision. The original policies also pin the SHA-256 of the grolifant and JUnit XML Parser JARs. [Archive coordinates, sources and digests](setup/archive-inputs.json) · [Strict resolution on both pins](setup/strict-resolution.json)

Run `python3 examples/437-gradle-named-actions/setup/full.py --fetch` to repeat the three dependency checks with a fresh offline Gradle cache for each pin. The full build uses the pins' own `:distributions-full:install` task and runs the same file and task-outcome observations on the installed binaries. Its receipt retains the stage and revision reached if a build stops. [Released distributions](setup/release-histories.json) · [Full pin-build job](../../verification/jobs/2026/11/25/20261125-190630-build-gradle-l15-with-three-verified-his.json)
