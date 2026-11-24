package retrofit2.converter.wire;

import java.lang.annotation.Annotation;
import java.util.Base64;
import okhttp3.RequestBody;
import okio.Buffer;
import retrofit2.Converter;
import retrofit2.Retrofit;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Retrofit retrofit = new Retrofit.Builder().baseUrl("http://localhost/")
                .addConverterFactory(WireConverterFactory.create()).build();
        Annotation[] none = {};
        Converter<Phone, RequestBody> converter = retrofit.requestBodyConverter(Phone.class, none, none);
        RequestBody body = converter.convert(new Phone(args[0]));
        Buffer buffer = new Buffer();
        body.writeTo(buffer);
        return Base64.getEncoder().encodeToString(buffer.readByteArray());
    }
}
