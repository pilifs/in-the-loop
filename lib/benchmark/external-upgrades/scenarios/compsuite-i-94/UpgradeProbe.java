import com.alibaba.citrus.service.form.impl.validation.DateValidatorTests;

public class UpgradeProbe {
    static final class FormRequest extends DateValidatorTests {
        String submit(String date) throws Exception {
            request(null, null, date);
            return field3.isValid() + "|" + field3.getMessage();
        }
    }

    public static String observe(String[] input) throws Exception {
        DateValidatorTests.initFactory();
        FormRequest form = new FormRequest();
        form.createWebClient();
        form.init();
        try {
            return form.submit(input[0]);
        } finally {
            form.commit();
        }
    }
}
