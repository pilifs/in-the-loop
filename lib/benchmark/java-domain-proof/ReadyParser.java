package campaign;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import java.io.IOException;

/** The complete observed initializer. No input has reached the factory's parser. */
public final class ReadyParser {
    static final JsonParser INSTANCE;
    static {
        try {
            INSTANCE = new JsonFactory().createNonBlockingByteArrayParser();
        } catch (IOException failure) {
            throw new ExceptionInInitializerError(failure);
        }
    }
}
