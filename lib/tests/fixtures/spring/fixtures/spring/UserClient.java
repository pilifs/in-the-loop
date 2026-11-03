package fixtures.spring;

import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.service.annotation.GetExchange;
import org.springframework.web.service.annotation.HttpExchange;

/** A declarative HTTP client: a call on it is an HTTP call. */
@HttpExchange("/users")
public interface UserClient {
    @GetExchange("/{id}")
    String user(@PathVariable String id);
}
