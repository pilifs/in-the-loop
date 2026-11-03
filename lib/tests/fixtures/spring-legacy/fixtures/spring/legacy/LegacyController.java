package fixtures.spring.legacy;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Compiled without {@code -parameters} (see the integration tests): the bytecode has no MethodParameters attribute,
 * so Spring 6.1 cannot name {@code id} and fails the request. {@code query} is named in its annotation and
 * {@code all} takes every parameter, so neither needs the name.
 */
@RestController
public class LegacyController {

    @GetMapping("/legacy/{id}")
    public String get(@PathVariable String id, @RequestParam("q") String query, @RequestParam Map<String, String> all) {
        return id + query + all.size();
    }
}
