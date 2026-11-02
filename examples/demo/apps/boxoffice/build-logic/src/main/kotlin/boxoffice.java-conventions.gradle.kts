// Every module: Java 25, strict compiler warnings, JUnit 5, and versions from the Spring Boot BOM.
plugins {
    `java-library`
}

group = "net.terminalvalue.boxoffice"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

val libs = versionCatalogs.named("libs")

dependencies {
    val bom = platform(libs.findLibrary("spring-boot-dependencies").get())
    implementation(bom)
    testImplementation(bom)
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("org.assertj:assertj-core")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.compilerArgs.addAll(listOf("-Xlint:all,-processing,-serial", "-Werror", "-parameters"))
}

tasks.withType<Test>().configureEach {
    useJUnitPlatform()
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
