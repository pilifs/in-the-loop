package net.terminalvalue.boxoffice.ticketing.store;

import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import net.terminalvalue.boxoffice.ticketing.domain.OrderStatus;
import net.terminalvalue.boxoffice.ticketing.domain.SeatStatus;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.index.Index;
import org.springframework.data.mongodb.core.index.PartialIndexFilter;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Repository;

/**
 * All reads and writes of the ticketing database. Every status change is a conditional update ("set X where the
 * status is still Y"), so concurrent writers cannot both succeed, whether or not they share a transaction.
 */
@Repository
public class TicketingStore {

    private final MongoTemplate mongo;

    public TicketingStore(MongoTemplate mongo) {
        this.mongo = mongo;
        mongo.indexOps(SeatDocument.class).createIndex(new Index().on("concertId", Sort.Direction.ASC));
        mongo.indexOps(SeatDocument.class).createIndex(new Index().on("holdId", Sort.Direction.ASC));
        mongo.indexOps(SeatDocument.class)
                .createIndex(new Index().on("status", Sort.Direction.ASC).on("expiresAt", Sort.Direction.ASC));
        mongo.indexOps(HoldDocument.class)
                .createIndex(new Index()
                        .on("customerId", Sort.Direction.ASC)
                        .on("idempotencyKey", Sort.Direction.ASC)
                        .unique()
                        .partial(PartialIndexFilter.of(where("idempotencyKey").exists(true))));
        // One order per hold: a retried POST /orders finds the first order instead of charging twice.
        mongo.indexOps(OrderDocument.class).createIndex(new Index().on("holdId", Sort.Direction.ASC).unique());
    }

    // Concerts

    public void insert(ConcertDocument concert) {
        mongo.insert(concert);
        mongo.insert(
                concert.seatLabels().stream()
                        .map(label -> new SeatDocument(
                                SeatDocument.id(concert.id(), label),
                                concert.id(),
                                label,
                                SeatStatus.AVAILABLE,
                                null,
                                null,
                                null))
                        .toList(),
                SeatDocument.class);
    }

    public Optional<ConcertDocument> concert(String id) {
        return Optional.ofNullable(mongo.findById(id, ConcertDocument.class));
    }

    public List<SeatDocument> seats(String concertId) {
        return mongo.find(query(where("concertId").is(concertId)), SeatDocument.class);
    }

    // Seats

    /**
     * Holds the seats that a new hold may take ({@link SeatStatus#isHoldable}) and returns how many it took. The
     * caller rolls back unless that is all of them.
     */
    public long hold(String concertId, List<String> labels, String holdId, Instant expiresAt, Instant now) {
        var holdable = new Criteria()
                .orOperator(
                        where("status").is(SeatStatus.AVAILABLE),
                        where("status").is(SeatStatus.HELD).and("expiresAt").lte(now));
        var seats = where("concertId").is(concertId).and("label").in(labels).andOperator(holdable);
        var update = new Update()
                .set("status", SeatStatus.HELD)
                .set("holdId", holdId)
                .set("expiresAt", expiresAt)
                .unset("orderId");
        return mongo.updateMulti(query(seats), update, SeatDocument.class).getModifiedCount();
    }

    /** The number of seats that {@code holdId} still holds, whether or not its expiry time has passed. */
    public long heldBy(String holdId) {
        return mongo.count(query(where("holdId").is(holdId).and("status").is(SeatStatus.HELD)), SeatDocument.class);
    }

    /** The number of seats that {@code holdId} holds and that have not expired at {@code now}. */
    public long heldUnexpiredBy(String holdId, Instant now) {
        return mongo.count(
                query(where("holdId").is(holdId).and("status").is(SeatStatus.HELD).and("expiresAt").gt(now)),
                SeatDocument.class);
    }

    /** Sells every seat that {@code holdId} still holds to {@code orderId}, and returns how many. */
    public long sell(String holdId, String orderId) {
        return mongo.updateMulti(
                        query(where("holdId").is(holdId).and("status").is(SeatStatus.HELD)),
                        new Update().set("status", SeatStatus.SOLD).set("orderId", orderId).unset("expiresAt"),
                        SeatDocument.class)
                .getModifiedCount();
    }

    /** Releases the seats that {@code holdId} holds or that are sold to {@code orderId}. */
    public long release(String holdId, String orderId) {
        var ours = new Criteria()
                .orOperator(
                        where("holdId").is(holdId).and("status").is(SeatStatus.HELD),
                        where("orderId").is(orderId).and("status").is(SeatStatus.SOLD));
        return mongo.updateMulti(query(ours), makeAvailable(), SeatDocument.class).getModifiedCount();
    }

    /** Releases every hold whose expiry time has passed. Each seat is released by its own atomic update. */
    public long releaseExpired(Instant now) {
        return mongo.updateMulti(
                        query(where("status").is(SeatStatus.HELD).and("expiresAt").lte(now)),
                        makeAvailable(),
                        SeatDocument.class)
                .getModifiedCount();
    }

    private static Update makeAvailable() {
        return new Update()
                .set("status", SeatStatus.AVAILABLE)
                .unset("holdId")
                .unset("expiresAt")
                .unset("orderId");
    }

    // Holds

    public void insert(HoldDocument hold) {
        mongo.insert(hold);
    }

    public Optional<HoldDocument> hold(String id) {
        return Optional.ofNullable(mongo.findById(id, HoldDocument.class));
    }

    public Optional<HoldDocument> holdByIdempotencyKey(String customerId, String key) {
        return Optional.ofNullable(mongo.findOne(
                query(where("customerId").is(customerId).and("idempotencyKey").is(key)), HoldDocument.class));
    }

    // Orders

    public void insert(OrderDocument order) {
        mongo.insert(order);
    }

    public Optional<OrderDocument> order(String id) {
        return Optional.ofNullable(mongo.findById(id, OrderDocument.class));
    }

    public Optional<OrderDocument> orderForHold(String holdId) {
        return Optional.ofNullable(mongo.findOne(query(where("holdId").is(holdId)), OrderDocument.class));
    }

    /** Moves the order from {@code from} to {@code to}, unless its status is no longer {@code from}. */
    public boolean transition(String orderId, OrderStatus from, OrderStatus to, Instant now) {
        return mongo.updateFirst(
                                query(where("_id").is(orderId).and("status").is(from)),
                                new Update().set("status", to).set("updatedAt", now),
                                OrderDocument.class)
                        .getModifiedCount()
                == 1;
    }
}
