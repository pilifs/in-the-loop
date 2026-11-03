package fixtures.spring;

import org.springframework.data.mongodb.core.mapping.Document;

/** A storage shape that a handler returns as is. */
@Document("notes")
public record NoteDocument(String id, String text) {}
