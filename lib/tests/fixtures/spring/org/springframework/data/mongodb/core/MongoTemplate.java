package org.springframework.data.mongodb.core;

import java.util.List;
import org.springframework.data.mongodb.core.index.IndexOperations;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;

/** The template's shape: the entity class is a parameter of every operation. */
public class MongoTemplate {
    public <T> List<T> find(Query query, Class<T> entityClass) { return List.of(); }
    public <T> T findOne(Query query, Class<T> entityClass) { return null; }
    public <T> T findById(Object id, Class<T> entityClass) { return null; }
    public boolean exists(Query query, Class<?> entityClass) { return false; }
    public long count(Query query, Class<?> entityClass) { return 0; }
    public long updateFirst(Query query, Update update, Class<?> entityClass) { return 0; }
    public long updateMulti(Query query, Update update, Class<?> entityClass) { return 0; }
    public <T> T insert(T object) { return object; }
    public IndexOperations indexOps(Class<?> entityClass) { return index -> ""; }
}
