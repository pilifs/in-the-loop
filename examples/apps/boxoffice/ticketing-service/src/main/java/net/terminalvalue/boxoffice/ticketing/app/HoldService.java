package net.terminalvalue.boxoffice.ticketing.app;

import java.time.Clock;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.ticketing.domain.HoldPolicy;
import net.terminalvalue.boxoffice.ticketing.store.HoldDocument;
import net.terminalvalue.boxoffice.ticketing.store.TicketingStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * Holds seats for a customer, synchronously: the response says whether the customer has the seats. A hold is a
 * lease. It lasts {@link HoldPolicy#ttl()}, after which the seats may be taken by someone else.
 */
@Service
public class HoldService {

    private static final Logger log = LoggerFactory.getLogger(HoldService.class);

    private final TicketingStore store;
    private final Transactions transactions;
    private final HoldPolicy policy;
    private final Clock clock;

    public HoldService(TicketingStore store, Transactions transactions, HoldPolicy policy, Clock clock) {
        this.store = store;
        this.transactions = transactions;
        this.policy = policy;
        this.clock = clock;
    }

    /**
     * Holds all of {@code labels}, or none of them. With an idempotency key, a repeated request returns the hold
     * that the first one created, even after it expired.
     */
    public Created<HoldDocument> hold(String concertId, String customerId, List<String> labels, String idempotencyKey) {
        try {
            policy.validate(labels);
        } catch (IllegalArgumentException e) {
            throw new InvalidRequestException(e.getMessage());
        }
        return transactions.run(() -> {
            if (idempotencyKey != null) {
                var earlier = store.holdByIdempotencyKey(customerId, idempotencyKey);
                if (earlier.isPresent()) {
                    return new Created<>(earlier.get(), false);
                }
            }
            var concert = store.concert(concertId).orElseThrow(() -> new NotFoundException("no concert " + concertId));
            if (!new HashSet<>(concert.seatLabels()).containsAll(labels)) {
                throw new InvalidRequestException("the concert has no seat named in " + labels);
            }
            Instant now = clock.instant();
            var hold = new HoldDocument(
                    UUID.randomUUID().toString(),
                    concertId,
                    List.copyOf(labels),
                    customerId,
                    HoldPolicy.totalCents(concert.priceCents(), labels.size()),
                    now,
                    policy.expiresAt(now),
                    idempotencyKey);
            long taken = store.hold(concertId, labels, hold.id(), hold.expiresAt(), now);
            if (taken != labels.size()) {
                // Throwing rolls back the seats this hold did take.
                throw new ConflictException("some of the seats " + labels + " are not available");
            }
            store.insert(hold);
            return new Created<>(hold, true);
        });
    }

    public HoldDocument get(String holdId) {
        return store.hold(holdId).orElseThrow(() -> new NotFoundException("no hold " + holdId));
    }

    /**
     * Releases expired holds. Correctness does not depend on this: a new hold already treats an expired seat as free.
     * The sweep keeps the stored status honest for readers and for the order flow.
     */
    @Scheduled(fixedDelayString = "${boxoffice.hold.sweep-interval:1s}")
    public void releaseExpiredHolds() {
        long released = store.releaseExpired(clock.instant());
        if (released > 0) {
            log.info("Released {} seats whose hold expired", released);
        }
    }
}
