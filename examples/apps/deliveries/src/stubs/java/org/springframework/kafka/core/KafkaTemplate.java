// A stand-in for the framework class of the same name, so that the app compiles without the framework on the class
// path. jvmcontract reads only the binary names of the class and its methods, which are the real ones; the app's
// tests subclass it to record what the route sends.
package org.springframework.kafka.core;

public class KafkaTemplate<K, V> {
    public Object send(String topic, V data) { return null; }
    public Object send(String topic, K key, V data) { return null; }
}
