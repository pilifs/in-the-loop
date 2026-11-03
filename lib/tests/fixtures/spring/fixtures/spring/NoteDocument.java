package fixtures.spring;

import java.time.Instant;
import java.util.List;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

/** A storage shape that a handler returns as is. The compound index names a field the record does not have. */
@Document("notes")
@CompoundIndex(def = "{'by': 1, 'created': -1}")
public record NoteDocument(@Id String id, String text, @Field("by") String author, @Indexed Instant createdAt, List<String> labels) {}
