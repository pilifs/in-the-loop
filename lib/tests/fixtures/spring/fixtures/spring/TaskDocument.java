package fixtures.spring;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Transient;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

/** A document with embedded types, a renamed field, a map and a transient component. */
@Document("tasks")
public record TaskDocument(
        @Id String id,
        String title,
        Assignee assignee,
        List<Step> steps,
        @Field("due") Instant dueAt,
        Instant createdAt,
        Map<String, String> labels,
        @Transient int cached) {
    public record Assignee(String name, String email) {}

    public record Step(String label, boolean done) {}
}
