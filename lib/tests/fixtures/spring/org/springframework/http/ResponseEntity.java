// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads the status the handler passes its builder.
package org.springframework.http;

public class ResponseEntity<T> {
    public static BodyBuilder status(int code) {
        return new BodyBuilder();
    }

    public static BodyBuilder status(HttpStatusCode code) {
        return new BodyBuilder();
    }

    public static BodyBuilder notFound() {
        return new BodyBuilder();
    }

    public static class BodyBuilder {
        public <T> ResponseEntity<T> build() {
            return new ResponseEntity<>();
        }

        public <T> ResponseEntity<T> body(T body) {
            return new ResponseEntity<>();
        }
    }
}
