package fixtures.spring;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.client.RestClient;

/** What each flow reaches: a document, a topic, an event, a table, a URL, through lambdas, interfaces and helpers. */
@Service
public class TaskFlow {
    private final MongoTemplate mongo;
    private final NotesStore store;
    private final NoteRepository notes;
    private final KafkaTemplate<String, String> kafka;
    private final ApplicationEventPublisher events;
    private final Notifier notifier;
    private final UserClient users;
    private final RestClient client;
    private final JdbcTemplate jdbc;
    private final TransactionTemplate transactions;
    private final Work work = new Work();

    public TaskFlow(MongoTemplate mongo, NotesStore store, NoteRepository notes, KafkaTemplate<String, String> kafka, ApplicationEventPublisher events, Notifier notifier, UserClient users, RestClient client, JdbcTemplate jdbc, TransactionTemplate transactions) {
        this.mongo = mongo;
        this.store = store;
        this.notes = notes;
        this.kafka = kafka;
        this.events = events;
        this.notifier = notifier;
        this.users = users;
        this.client = client;
        this.jdbc = jdbc;
        this.transactions = transactions;
    }

    /** Inside a lambda: the write (typed by the local variable), the send and the event are still reached. */
    public String create(String title) {
        return work.run(() -> {
            var task = new TaskDocument(title, title, null, List.of(), null, Instant.EPOCH, Map.of(), 0);
            mongo.insert(task);
            kafka.send("tasks", task.id());
            events.publishEvent(new TaskCreated(task.id()));
            return task.id();
        });
    }

    /** Through another bean's method: the find names its class. */
    public long open(String email) {
        return store.openTasksOf(email).size();
    }

    /** A derived repository delete, a deleting query, and a send behind an interface. */
    public void archive(String author) {
        notes.deleteByAuthor(author);
        notes.purge(author);
        notifier.notify(author);
    }

    /** A repository read: the domain type comes from the interface's generic supertype. */
    public boolean exists(String id) {
        return notes.findById(id).isPresent();
    }

    /** A read-only transaction that writes a table: the write is dropped or rejected. */
    @Transactional(readOnly = true)
    public long audit(String id) {
        jdbc.update("insert into audit(id, at) values (?, now())", id);
        return jdbc.queryForObject("select count(*) from notes where author = ?", Long.class, id);
    }

    /** A transaction that sends and calls out: neither is part of it. */
    @Transactional
    public void rename(String id, String title) {
        mongo.save(new TaskDocument(id, title, null, List.of(), null, Instant.EPOCH, Map.of(), 0));
        kafka.send("tasks", id);
        client.post().uri("/audit/{id}", id).retrieve().body(String.class);
    }

    /** The lambda runs inside the transaction a helper opens through TransactionTemplate: the send is inside it. */
    public String close(String id) {
        return work.atomically(transactions, () -> {
            mongo.remove(new TaskDocument(id, id, null, List.of(), null, Instant.EPOCH, Map.of(), 0));
            kafka.send("tasks", id);
            return id;
        });
    }

    /** Two HTTP calls: a declarative client and the fluent one. */
    public String owner(String id) {
        return users.user(id) + client.get().uri("/profiles/{id}", id).retrieve().body(String.class);
    }
}
