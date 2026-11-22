package campaign;

import org.apache.avro.NameValidator;

/** Ordinary entry through the original validator API available in Avro #3730. */
public final class UtfNameChecks {
    public static int names(int code) {
        NameValidator.Result result = NameValidator.UTF_VALIDATOR.validate(NameChecks.name(code));
        if (code < 14) return result == NameValidator.OK && result.isOK() ? 1 : 0;
        return !result.isOK() && result.getErrors() != null ? 1 : 0;
    }
}
