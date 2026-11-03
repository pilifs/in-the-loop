package fixtures.spring;

import com.fasterxml.jackson.annotation.JsonTypeInfo;

/** The Java class name on the wire. */
@JsonTypeInfo(use = JsonTypeInfo.Id.CLASS)
public interface Audit {
    record Login(String user) implements Audit {}
}
