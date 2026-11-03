// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the class and its methods, which are the real ones.
package org.springframework.web.client;

/** The fluent client: the verb is one call, the URI the next. */
public interface RestClient {
    RequestHeadersUriSpec get();
    RequestBodyUriSpec post();

    interface RequestHeadersUriSpec {
        RequestHeadersSpec uri(String uri, Object... variables);
    }

    interface RequestBodyUriSpec extends RequestHeadersUriSpec {}

    interface RequestHeadersSpec {
        ResponseSpec retrieve();
    }

    interface ResponseSpec {
        <T> T body(Class<T> type);
    }
}
