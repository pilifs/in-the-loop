package org.springframework.data.mongodb.repository;

import java.util.Optional;

public interface MongoRepository<T, ID> {
    Optional<T> findById(ID id);
    <S extends T> S save(S entity);
}
