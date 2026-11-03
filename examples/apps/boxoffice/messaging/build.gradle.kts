// Reliable messaging shared by the services: transactional outbox, idempotent inbox, Kafka error handling.
plugins {
    id("boxoffice.java-conventions")
    id("boxoffice.boundaries")
}

dependencies {
    api(project(":contracts"))
    api("org.springframework.boot:spring-boot-starter-data-mongodb")
    api("org.springframework.boot:spring-boot-starter-kafka")
}
