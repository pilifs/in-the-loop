// A stand-in for the framework enum of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads the constant's name at the use site.
package org.springframework.http;

public enum HttpStatus implements HttpStatusCode {
    OK, BAD_REQUEST, NOT_FOUND, CONFLICT, GONE, UNPROCESSABLE_CONTENT, INTERNAL_SERVER_ERROR, SERVICE_UNAVAILABLE, CREATED;

    @Override
    public int value() {
        return 0;
    }
}
