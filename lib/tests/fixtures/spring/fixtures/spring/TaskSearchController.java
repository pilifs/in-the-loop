package fixtures.spring;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/** Two routes {@link TasksController} also claims: one identical, one the same pattern under another variable name. */
@RestController
public class TaskSearchController {

    /** Identical to TasksController.open: Spring refuses the duplicate at startup. */
    @GetMapping("/tasks/open")
    public long open() {
        return 0;
    }

    /** The same pattern as TasksController.owner with the variable renamed: every request that matches is ambiguous. */
    @GetMapping("/tasks/{key}/owner")
    public String owner(@PathVariable String key) {
        return key;
    }
}
