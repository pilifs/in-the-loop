// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads the status the handler passes it.
package org.springframework.http;

public class ProblemDetail {
    public static ProblemDetail forStatus(HttpStatusCode status) {
        return new ProblemDetail();
    }

    public static ProblemDetail forStatusAndDetail(HttpStatusCode status, String detail) {
        return new ProblemDetail();
    }
}
