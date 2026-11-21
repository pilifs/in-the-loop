package retrofit2.converter.wire;

import java.util.Base64;
import okhttp3.RequestBody;
import okio.Buffer;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Phone phone = new Phone.Builder().number(args[0]).build();
        WireRequestBodyConverter<Phone> converter = new WireRequestBodyConverter<>(Phone.ADAPTER);
        RequestBody encoded = converter.convert(phone);
        Buffer out = new Buffer();
        encoded.writeTo(out);
        return Base64.getEncoder().encodeToString(out.readByteArray());
    }
}
