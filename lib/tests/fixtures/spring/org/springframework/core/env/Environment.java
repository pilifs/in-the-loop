// A stand-in for the framework interface of the same name, so that the fixtures compile without the framework on
// the class path. jvmcontract reads only the owner and name of the methods the fixtures call.
package org.springframework.core.env;

public interface Environment {
    boolean containsProperty(String key);

    String getProperty(String key);

    String getProperty(String key, String defaultValue);

    <T> T getProperty(String key, Class<T> targetType);

    String getRequiredProperty(String key);
}
