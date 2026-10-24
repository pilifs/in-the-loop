package net.terminalvalue.boxoffice.payments.api;

import java.util.List;
import net.terminalvalue.boxoffice.payments.app.PaymentDocument;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Read-only view of the payment ledger, for operators and for checking the system's invariants. */
@RestController
@RequestMapping("/payments")
class PaymentController {

    private final MongoTemplate mongo;

    PaymentController(MongoTemplate mongo) {
        this.mongo = mongo;
    }

    @GetMapping
    List<PaymentDocument> all() {
        return mongo.find(new Query().with(Sort.by("createdAt")), PaymentDocument.class);
    }

    @GetMapping("/{orderId}")
    ResponseEntity<PaymentDocument> get(@PathVariable String orderId) {
        return ResponseEntity.ofNullable(mongo.findById(orderId, PaymentDocument.class));
    }
}
