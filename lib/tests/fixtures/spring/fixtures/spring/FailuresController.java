package fixtures.spring;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Each route's throws line says what becomes of each exception; one of them nothing maps. */
@RestController
@RequestMapping("/failures")
public class FailuresController {
    private final FailureFlow flow;

    public FailuresController(FailureFlow flow) {
        this.flow = flow;
    }

    @GetMapping("/{id}")
    public String find(@PathVariable String id) {
        return flow.find(id);
    }

    /** An application exception nothing maps, and an `IllegalArgumentException` the advice takes. */
    @PostMapping("/{id}/expiry")
    public void expire(@PathVariable String id) {
        flow.check(id);
        flow.expire(id);
    }

    /** Swallowed in the flow: nothing to say. */
    @PostMapping("/{id}/guarded")
    public void guarded(@PathVariable String id) {
        flow.guarded(id);
    }

    /** Rethrown by the flow's catch, so it still reaches the route. */
    @PostMapping("/{id}/retried")
    public void retried(@PathVariable String id) {
        flow.retried(id);
    }

    /** The wrapper goes to the controller's own handler, which answers 503. */
    @PostMapping("/{id}/wrapped")
    public void wrapped(@PathVariable String id) {
        flow.wrapped(id);
        flow.later(id);
    }

    @GetMapping("/{id}/gone")
    public String gone(@PathVariable String id) {
        return flow.gone(id);
    }

    @GetMapping("/{id}/pick")
    public String pick(@PathVariable String id) {
        return flow.pick(java.util.Optional.of(id));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Void> unavailable(IllegalStateException e) {
        return ResponseEntity.status(503).build();
    }
}
