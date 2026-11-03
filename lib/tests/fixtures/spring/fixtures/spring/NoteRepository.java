package fixtures.spring;

import java.util.List;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;

/** Repository queries: the JSON names fields, and one of them is wrong. */
public interface NoteRepository extends MongoRepository<NoteDocument, String> {
    @Query(value = "{ 'author': ?0, 'labels': { '$in': ?1 } }", sort = "{ 'createdAt': -1 }")
    List<NoteDocument> byAuthor(String author, List<String> labels);

    @Query(value = "{ 'txet': ?0 }", fields = "{ 'text': 1, 'by': 1 }")
    List<NoteDocument> search(String text);
}
