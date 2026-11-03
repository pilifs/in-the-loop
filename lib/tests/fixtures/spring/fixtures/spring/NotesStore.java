package fixtures.spring;

import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.util.List;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.index.Index;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Component;

/** Queries, updates, indexes and sorts over the documents, with one wrong field name of each kind. */
@Component
public class NotesStore {
    private final MongoTemplate mongo;

    public NotesStore(MongoTemplate mongo) {
        this.mongo = mongo;
        mongo.indexOps(NoteDocument.class).createIndex(new Index().on("createdAt", Sort.Direction.ASC));
        mongo.indexOps(NoteDocument.class).createIndex(new Index().on("created", Sort.Direction.ASC));
    }

    public List<NoteDocument> byAuthor(String author) {
        return mongo.find(
                query(where("by").is(author)).with(Sort.by(Sort.Direction.DESC, "createdAt", "author")),
                NoteDocument.class);
    }

    public long rename(String id, String text) {
        return mongo.updateFirst(
                query(where("_id").is(id).and("txt").is(text)),
                new Update().set("text", text).set("views", 1).unset("labels"),
                NoteDocument.class);
    }

    public List<TaskDocument> openTasksOf(String email) {
        var open = where("assignee.email").is(email)
                .and("steps.done").is(false)
                .and("labels.team").is("core")
                .and("assignee.mail").is(email)
                .and("steps.0.label").is("start")
                .and("assignee.email.domain").is("example.org");
        return mongo.find(query(open).with(Sort.by("titel")), TaskDocument.class);
    }

    public long finish(String id) {
        return mongo.updateFirst(query(where("id").is(id)), done(), TaskDocument.class);
    }

    /** No document named here: the callers' documents are the scope. */
    private static Update done() {
        return new Update().set("steps.$.done", true).unset("archived").currentDate("due");
    }

    /** No document named here or in a caller: every document of the module is the scope. */
    public Query anywhere() {
        return query(where("nowhere").is(1));
    }

    public long bump(String id) {
        return mongo.updateFirst(
                query(where("_id").is(id)), new Update().inc("value", 1).inc("valeu", 1), CounterDocument.class);
    }
}
