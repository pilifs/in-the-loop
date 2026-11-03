// A stand-in for the framework interface of the same name, so that the fixtures compile without the framework on
// the class path.
package org.springframework.http;

public interface HttpStatusCode {
    int value();

    static HttpStatusCode valueOf(int code) {
        return () -> code;
    }
}
