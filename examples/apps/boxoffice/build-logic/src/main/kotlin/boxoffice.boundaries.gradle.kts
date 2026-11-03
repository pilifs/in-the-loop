// The module's boundary contract (src/contract/boundaries.contract): where Spring enters the module (routes,
// listeners, schedules, bean definitions), the advice on each bean, the places where an annotation does not do
// what it says, the configuration keys (what the classes read, what application.yaml sets, what the class path's
// metadata declares), the wire types (the JSON shape of each request, response and message) and the stored types
// (the shape of each Mongo document, with the query strings that name a field it does not have), and under each
// entry point what it reaches (reads, writes, sends, calls, publishes; a send from inside a transaction is a `!`
// line, and so is a @PathVariable that names no variable of its route). `check` fails
// when the compiled classes or the application files no longer match it, and
// `updateBoundaries` rewrites it from the code. The verifier is jvmcontract, the Rust tool in lib/, which reads the
// class files directly; the tasks are skipped when it is not on the PATH, so the build still works without it.
plugins {
    java
}

val contractsDir = layout.projectDirectory.dir("src/contract")
val reportDir = layout.buildDirectory.dir("reports/contracts")

fun onPath(program: String): Boolean =
    System.getenv("PATH").orEmpty().split(File.pathSeparator).any { File(it, program).canExecute() }

// Everything the task needs is captured here as plain values and providers, so that the task serializes into
// Gradle's configuration cache; the command line itself is assembled at execution time.
fun Exec.configureBoundaries(mode: String) {
    group = "verification"
    dependsOn("classes")
    val available = onPath("jvmcontract")
    onlyIf("jvmcontract is on the PATH") { available }
    val classes: FileCollection = sourceSets.main.get().output.classesDirs
    val classpath: Provider<String> = configurations.runtimeClasspath.map { it.asPath }
    val sources: List<String> = sourceSets.main.get().java.srcDirs.map { it.path }
    val resources: List<String> = sourceSets.main.get().resources.srcDirs.map { it.path }
    val moduleName = project.name
    val root = rootDir.path
    val contracts = contractsDir.asFile.path
    val report = reportDir.get().asFile.path
    inputs.files(classes)
    inputs.files(resources.map { fileTree(it) })
    doFirst {
        val args = mutableListOf("jvmcontract", mode, "--contracts", contracts, "--module", moduleName)
        classes.forEach { args += listOf("--classes", it.path) }
        args += listOf("--classpath", classpath.get())
        sources.forEach { args += listOf("--sources", it) }
        resources.forEach { args += listOf("--resources", it) }
        args += listOf("--base", root, "--report", report)
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
