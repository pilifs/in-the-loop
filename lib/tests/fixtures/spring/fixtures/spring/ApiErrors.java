package fixtures.spring;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** The advice: a handler per application exception, one of them twice. */
@RestControllerAdvice
public class ApiErrors {
    /** The status is the constant the body passes on. */
    @ExceptionHandler
    public ProblemDetail missing(MissingException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
    }

    /** The status is the annotation's. */
    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public void invalid() {
    }

    /** A second handler for a type the first one takes: Spring refuses it at startup. */
    @ExceptionHandler
    public ResponseEntity<String> missingAgain(MissingException e) {
        return ResponseEntity.notFound().build();
    }
}
