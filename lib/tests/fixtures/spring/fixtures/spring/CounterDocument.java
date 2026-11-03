package fixtures.spring;

import org.springframework.data.annotation.Version;
import org.springframework.data.mongodb.core.mapping.Document;

/** A class document: the id is the field named id, the collection is the class name, transient and static fields are not stored. */
@Document
public class CounterDocument {
    private static final int LIMIT = 10;
    private String id;
    private long value;
    private transient long cached;
    @Version
    private Long version;

    public long next() {
        return Math.min(++value, LIMIT);
    }
}
