// The module's boundary contract (src/contract/boundaries.contract): where Spring enters the module (routes,
// listeners, schedules, bean definitions, configuration keys), the advice on each bean, and the places where an
// annotation does not do what it says. `check` fails when the compiled classes no longer match it, and
// `updateBoundaries` rewrites it from the code. The verifier is jvmcontract, the Rust tool in lib/, which reads the
// class files directly; the tasks are skipped when it is not on the PATH, so the build still works without it.
plugins {
    java
}

val contractsDir = layout.projectDirectory.dir("src/contract")
val reportDir = layout.buildDirectory.dir("reports/contracts")

fun onPath(program: String): Boolean =
    System.getenv("PATH").orEmpty().split(File.pathSeparator).any { File(it, program).canExecute() }

fun Exec.configureBoundaries(mode: String) {
    group = "verification"
    dependsOn("classes")
    onlyIf("jvmcontract is on the PATH") { onPath("jvmcontract") }
    val classes = sourceSets.main.get().output.classesDirs
    val classpath = configurations.runtimeClasspath.get()
    inputs.files(classes)
    doFirst {
        val args = mutableListOf("jvmcontract", mode, "--contracts", contractsDir.asFile.path, "--module", project.name)
        classes.forEach { args += listOf("--classes", it.path) }
        args += listOf("--classpath", classpath.asPath)
        sourceSets.main.get().java.srcDirs.forEach { args += listOf("--sources", it.path) }
        args += listOf("--base", rootDir.path, "--report", reportDir.get().asFile.path)
        if (mode == "update") args += listOf("--add", "boundaries")
        commandLine(args)
    }
}

val verifyBoundaries = tasks.register<Exec>("verifyBoundaries") {
    description = "Checks that the module's Spring boundaries still match src/contract/boundaries.contract."
    configureBoundaries("verify")
    inputs.dir(contractsDir).optional()
    outputs.dir(reportDir)
}

tasks.named("check") {
    dependsOn(verifyBoundaries)
}

tasks.register<Exec>("updateBoundaries") {
    description = "Rewrites src/contract/boundaries.contract from the code."
    configureBoundaries("update")
}
