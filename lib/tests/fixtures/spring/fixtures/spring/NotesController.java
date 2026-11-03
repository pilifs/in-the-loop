package fixtures.spring;

import java.util.List;
import java.util.Map;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/** The wire types come from the handlers' bodies and results, and from the listener's payload. */
@RestController
public class NotesController {
    @PostMapping("/notes")
    public Note create(@RequestBody Note note) { return note; }

    @GetMapping("/notes/{id}")
    public Map<String, List<NoteDocument>> get(@PathVariable Kind kind) { return Map.of(); }

    @KafkaListener(topics = "audit")
    public void on(Audit audit) {}
}
