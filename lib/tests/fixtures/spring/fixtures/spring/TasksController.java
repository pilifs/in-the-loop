package fixtures.spring;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Each handler's reach lines come from {@link TaskFlow}; one GET has side effects. */
@RestController
public class TasksController {
    private final TaskFlow flow;

    public TasksController(TaskFlow flow) {
        this.flow = flow;
    }

    @PostMapping("/tasks")
    public String create(@RequestParam String title) {
        return flow.create(title);
    }

    @GetMapping("/tasks/open")
    public long open(@RequestParam String email) {
        return flow.open(email);
    }

    /** A GET that writes and sends: a safe method with side effects. */
    @GetMapping("/tasks/{author}/archive")
    public void archive(@PathVariable String author) {
        flow.archive(author);
    }

    /** A GET that only reads and calls other GETs: no problem. */
    @GetMapping("/tasks/{id}/owner")
    public String owner(@PathVariable String id) {
        return flow.exists(id) ? flow.owner(id) : "";
    }
}
