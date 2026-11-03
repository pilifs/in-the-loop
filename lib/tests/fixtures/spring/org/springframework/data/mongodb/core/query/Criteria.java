package org.springframework.data.mongodb.core.query;

/** The criteria's shape: `where` and `and` name fields, the operators take values. */
public class Criteria {
    public Criteria() {}
    public Criteria(String key) {}
    public static Criteria where(String key) { return new Criteria(key); }
    public Criteria and(String key) { return this; }
    public Criteria is(Object value) { return this; }
    public Criteria ne(Object value) { return this; }
    public Criteria lt(Object value) { return this; }
    public Criteria lte(Object value) { return this; }
    public Criteria gt(Object value) { return this; }
    public Criteria in(java.util.Collection<?> values) { return this; }
    public Criteria exists(boolean exists) { return this; }
    public Criteria orOperator(Criteria... criteria) { return this; }
    public Criteria andOperator(Criteria... criteria) { return this; }
}
