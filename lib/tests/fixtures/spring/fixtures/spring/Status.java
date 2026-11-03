package fixtures.spring;

import com.fasterxml.jackson.annotation.JsonValue;

public enum Status {
    OK(1), FAILED(2);

    private final int code;

    Status(int code) { this.code = code; }

    @JsonValue
    int code() { return code; }
}
