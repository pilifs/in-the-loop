// Behavioural and capability contracts (examples/tools/contracts): `check` fails when the bytecode no longer matches
// the contracts in src/contract, the way a static-analysis gate fails on a new issue. `updateContracts` rewrites them
// from the code; `updateContracts -Ptarget=<class>#<method>` adds a behavioural contract, and
// `updateContracts -Ptarget=capabilities` adds the module's capability contract.
plugins {
    java
}

val contractVerifier = configurations.dependencyScope("contractVerifier")
val contractVerifierClasspath = configurations.resolvable("contractVerifierClasspath") {
    extendsFrom(contractVerifier.get())
}

dependencies {
    "contractVerifier"("net.terminalvalue.contracts:contract-verifier:0.1.0")
}

val contractsDir = layout.projectDirectory.dir("src/contract")
val reportDir = layout.buildDirectory.dir("reports/contracts")
val toolchains = extensions.getByType<JavaToolchainService>()

fun JavaExec.configureVerifier(mode: String) {
    group = "verification"
    classpath(contractVerifierClasspath, sourceSets.main.get().runtimeClasspath)
    mainClass = "net.terminalvalue.contracts.Main"
    javaLauncher = toolchains.launcherFor { languageVersion = JavaLanguageVersion.of(25) }
    args(mode, "--contracts", contractsDir.asFile.path, "--module", project.name)
    sourceSets.main.get().output.classesDirs.forEach { args("--classes", it.path) }
    sourceSets.main.get().java.srcDirs.forEach { args("--sources", it.path) }
}

val verifyContracts = tasks.register<JavaExec>("verifyContracts") {
    description = "Checks that the code still behaves exactly as its contracts in src/contract say."
    configureVerifier("verify")
    args("--report", reportDir.get().asFile.path, "--base", rootDir.path)
    inputs.dir(contractsDir).optional()
    inputs.files(sourceSets.main.get().runtimeClasspath)
    outputs.dir(reportDir)
}

tasks.named("check") {
    dependsOn(verifyContracts)
}

tasks.register<JavaExec>("updateContracts") {
    description = "Rewrites the contracts in src/contract from the code. Add one with -Ptarget=<class>#<method>," +
            " or the module's capability contract with -Ptarget=capabilities."
    configureVerifier("update")
    providers.gradleProperty("target").orNull?.let { args("--add", it) }
}
