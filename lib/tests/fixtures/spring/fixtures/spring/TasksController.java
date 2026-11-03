package fixtures.spring;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
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

    /** The service method is @Transactional: it accounts for its own send and call, the route does not. */
    @PutMapping("/tasks/{id}")
    public void rename(@PathVariable String id, @RequestParam String title) {
        flow.rename(id, title);
    }

    /** The service method opens its transaction through a helper and a template: the route accounts for it. */
    @PostMapping("/tasks/{id}/close")
    public String close(@PathVariable String id) {
        return flow.close(id);
    }

    /** The template says {taskId}, the parameter says id: nothing binds it, a 500 on every request. */
    @DeleteMapping("/tasks/{taskId}")
    public void delete(@PathVariable String id) {
        flow.exists(id);
    }

    /** A page number the request may leave out, in an int: Spring cannot pass null for it. */
    @GetMapping("/tasks/page")
    public long page(@RequestParam(required = false) int page) {
        return page;
    }

    /** A GET that only reads and calls other GETs: no problem. */
    @GetMapping("/tasks/{id}/owner")
    public String owner(@PathVariable String id) {
        return flow.exists(id) ? flow.owner(id) : "";
    }
}
