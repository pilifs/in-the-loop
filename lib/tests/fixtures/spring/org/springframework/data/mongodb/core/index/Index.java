package org.springframework.data.mongodb.core.index;

import org.springframework.data.domain.Sort;

/** The index builder's shape: `on` names a field. */
public class Index {
    public Index() {}
    public Index(String key, Sort.Direction direction) {}
    public Index on(String key, Sort.Direction direction) { return this; }
    public Index named(String name) { return this; }
    public Index unique() { return this; }
}
