package retrofit2.converter.wire;

import java.util.Base64;
import okhttp3.MediaType;
import okhttp3.ResponseBody;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        byte[] wire = Base64.getDecoder().decode(args[0]);
        ResponseBody body = ResponseBody.create(MediaType.parse("application/x-protobuf"), wire);
        WireResponseBodyConverter<Phone> converter = new WireResponseBodyConverter<>(Phone.ADAPTER);
        return converter.convert(body).number;
    }
}
