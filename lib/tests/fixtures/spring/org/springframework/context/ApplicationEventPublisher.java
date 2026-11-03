// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the class and its methods, which are the real ones.
package org.springframework.context;

public interface ApplicationEventPublisher {
    void publishEvent(Object event);
}
