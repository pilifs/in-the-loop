package net.terminalvalue.boxoffice.contracts;

import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

/**
 * The JSON wire format of every message. Both services use this class, so they agree on the format whatever their
 * own Jackson settings are. The type is in the payload ({@code "type": "ChargePayment"}), not in a header that names
 * a Java class, so producers and consumers can be deployed independently.
 */
public final class MessageCodec {

    private static final JsonMapper MAPPER = JsonMapper.builder()
            .enable(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
            .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .build();

    private MessageCodec() {}

    public static String encode(Message message) {
        return MAPPER.writeValueAsString(message);
    }

    /** Throws {@link tools.jackson.core.JacksonException} for a payload that is not a {@code type}. */
    public static <T extends Message> T decode(String json, Class<T> type) {
        return MAPPER.readValue(json, type);
    }
}
