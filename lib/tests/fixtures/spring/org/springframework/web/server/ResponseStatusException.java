// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads the status it is built with.
package org.springframework.web.server;

import org.springframework.http.HttpStatusCode;

public class ResponseStatusException extends RuntimeException {
    public ResponseStatusException(HttpStatusCode status, String reason) {
        super(reason);
    }

    public ResponseStatusException(HttpStatusCode status) {
        super();
    }
}
