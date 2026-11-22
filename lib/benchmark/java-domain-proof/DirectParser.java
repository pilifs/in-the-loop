package campaign;

import com.fasterxml.jackson.core.ErrorReportConfiguration;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.StreamReadConstraints;
import com.fasterxml.jackson.core.StreamWriteConstraints;
import com.fasterxml.jackson.core.io.ContentReference;
import com.fasterxml.jackson.core.io.IOContext;
import com.fasterxml.jackson.core.json.async.NonBlockingJsonParser;
import com.fasterxml.jackson.core.sym.ByteQuadsCanonicalizer;
import com.fasterxml.jackson.core.util.BufferRecycler;

public final class DirectParser {
    static JsonParser create() {
        IOContext context = new IOContext(StreamReadConstraints.defaults(), StreamWriteConstraints.defaults(),
                ErrorReportConfiguration.defaults(), new BufferRecycler(), ContentReference.unknown(), false);
        ByteQuadsCanonicalizer symbols = ByteQuadsCanonicalizer.createRoot()
                .makeChildOrPlaceholder(JsonFactory.Feature.collectDefaults());
        return new NonBlockingJsonParser(context, JsonParser.Feature.collectDefaults(), symbols);
    }

    public static int oneRefill(int padding) throws java.io.IOException {
        // Split immediately after '['. The second fresh window contains 'true]'.
        return DirectTokens.correctOffsets(DirectTokens.trace(1, padding)) ? 1 : 0;
    }
}
