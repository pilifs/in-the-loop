package org.springframework.data.mongodb.core.query;

/** The update's shape: every operator names the field it writes or removes. */
public class Update {
    public static Update update(String key, Object value) { return new Update().set(key, value); }
    public Update set(String key, Object value) { return this; }
    public Update setOnInsert(String key, Object value) { return this; }
    public Update unset(String key) { return this; }
    public Update inc(String key, Number inc) { return this; }
    public Update push(String key, Object value) { return this; }
    public Update pull(String key, Object value) { return this; }
    public Update rename(String oldName, String newName) { return this; }
    public Update currentDate(String key) { return this; }
}
