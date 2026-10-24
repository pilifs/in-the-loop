package net.terminalvalue.boxoffice.ticketing.api;

import net.terminalvalue.boxoffice.ticketing.app.ConflictException;
import net.terminalvalue.boxoffice.ticketing.app.InvalidRequestException;
import net.terminalvalue.boxoffice.ticketing.app.NotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** Maps application errors to RFC 9457 problem responses. */
@RestControllerAdvice
class ApiErrors {

    @ExceptionHandler
    ProblemDetail notFound(NotFoundException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler
    ProblemDetail conflict(ConflictException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
    }

    @ExceptionHandler
    ProblemDetail invalid(InvalidRequestException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }
}
