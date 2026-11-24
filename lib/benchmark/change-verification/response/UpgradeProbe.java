package retrofit2.converter.wire;

import java.lang.annotation.Annotation;
import java.util.Base64;
import okhttp3.ResponseBody;
import okhttp3.MediaType;
import retrofit2.Converter;
import retrofit2.Retrofit;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Retrofit retrofit = new Retrofit.Builder().baseUrl("http://localhost/")
                .addConverterFactory(WireConverterFactory.create()).build();
        Annotation[] none = {};
        Converter<ResponseBody, Phone> converter = retrofit.responseBodyConverter(Phone.class, none);
        byte[] wire = Base64.getDecoder().decode(args[0]);
        return converter.convert(ResponseBody.create(MediaType.parse("application/x-protobuf"), wire)).number;
    }
}
