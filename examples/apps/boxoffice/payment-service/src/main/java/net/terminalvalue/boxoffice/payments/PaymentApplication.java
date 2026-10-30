package net.terminalvalue.boxoffice.payments;

import net.terminalvalue.boxoffice.messaging.MessagingConfiguration;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;

/** Charges and refunds orders through a payment gateway. Owns the {@code payments} database. */
@SpringBootApplication
@Import(MessagingConfiguration.class)
public class PaymentApplication {

    public static void main(String[] args) {
        SpringApplication.run(PaymentApplication.class, args);
    }
}
