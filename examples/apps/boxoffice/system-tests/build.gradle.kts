// End-to-end tests: both services in one JVM against real Kafka and MongoDB containers.
plugins {
    id("boxoffice.java-conventions")
}

dependencies {
    testImplementation(project(":contracts"))
    testImplementation(project(":ticketing-service"))
    testImplementation(project(":payment-service"))
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.boot:spring-boot-starter-webmvc")
    testImplementation("org.springframework.boot:spring-boot-starter-data-mongodb")
    testImplementation("org.springframework.boot:spring-boot-starter-kafka")
    testImplementation("org.testcontainers:testcontainers-junit-jupiter")
    testImplementation("org.testcontainers:testcontainers-kafka")
    testImplementation("org.testcontainers:testcontainers-mongodb")
    testImplementation("org.awaitility:awaitility")
}
