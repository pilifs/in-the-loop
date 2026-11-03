package org.springframework.data.mongodb.core.query;

import org.springframework.data.domain.Sort;

public class Query {
    public Query() {}
    public Query(Criteria criteria) {}
    public static Query query(Criteria criteria) { return new Query(criteria); }
    public Query with(Sort sort) { return this; }
    public Field fields() { return new Field(); }
}
