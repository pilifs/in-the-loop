package fixtures.spring;

import com.fasterxml.jackson.annotation.JsonProperty;

public enum Kind {
    @JsonProperty("small") SMALL,
    LARGE
}
