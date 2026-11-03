package fixtures.spring;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

/** An application exception that carries its own status. */
@ResponseStatus(HttpStatus.CONFLICT)
public class StaleException extends RuntimeException {
    public StaleException(String message) {
        super(message);
    }
}
