pluginManagement {
    includeBuild("build-logic")
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

rootProject.name = "boxoffice"

include(
    "contracts",
    "messaging",
    "ticketing-domain",
    "ticketing-service",
    "payment-service",
    "system-tests",
)
