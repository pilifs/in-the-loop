// The messages that services exchange over Kafka, and their JSON encoding.
plugins {
    id("boxoffice.java-conventions")
    id("boxoffice.contracts")
    id("boxoffice.boundaries")
}

dependencies {
    api("tools.jackson.core:jackson-databind")
}
