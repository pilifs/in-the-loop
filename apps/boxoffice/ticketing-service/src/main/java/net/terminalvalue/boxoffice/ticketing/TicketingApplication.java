package net.terminalvalue.boxoffice.ticketing;

import java.time.Duration;
import net.terminalvalue.boxoffice.messaging.MessagingConfiguration;
import net.terminalvalue.boxoffice.ticketing.domain.HoldPolicy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

/** Concerts, seat holds and orders. Owns the {@code ticketing} database; talks to payments only through Kafka. */
@SpringBootApplication
@Import(MessagingConfiguration.class)
public class TicketingApplication {

    public static void main(String[] args) {
        SpringApplication.run(TicketingApplication.class, args);
    }

    @Bean
    HoldPolicy holdPolicy(
            @Value("${boxoffice.hold.max-seats:8}") int maxSeats, @Value("${boxoffice.hold.ttl:2m}") Duration ttl) {
        return new HoldPolicy(maxSeats, ttl);
    }
}
