package org.springframework.data.mongodb.core.query;

/** The projection's shape: `include` and `exclude` name fields. */
public class Field {
    public Field include(String field) { return this; }
    public Field include(String... fields) { return this; }
    public Field exclude(String field) { return this; }
    public Field exclude(String... fields) { return this; }
}
