import java.util.Map;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.bind.BindException;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.bind.validation.BindValidationException;
import org.springframework.boot.context.properties.bind.validation.ValidationBindHandler;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.validation.FieldError;
import org.springframework.validation.annotation.Validated;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

public class PublicCaller {
    @Validated
    public static class Wild {
        private Map<String, ?> params;
        public Map<String, ?> getParams() { return params; }
        public void setParams(Map<String, ?> params) { this.params = params; }
    }
    @Validated
    public static class Age {
        @Min(5) private int age;
        public int getAge() { return age; }
        public void setAge(int age) { this.age = age; }
    }
    @Validated
    public static class Both extends Wild {
        @Min(10) private int age;
        public int getAge() { return age; }
        public void setAge(int age) { this.age = age; }
    }

    static String bind(String root, Map<String, String> props, Class<?> type) {
        try (var validator = new LocalValidatorFactoryBean()) {
            validator.afterPropertiesSet();
            var handler = new ValidationBindHandler(validator);
            Object bean = new Binder(new MapConfigurationPropertySource(props)).bind(root, Bindable.of(type), handler).get();
            if (bean instanceof Both both) return both.getParams().get("toto") + ":" + both.getAge();
            if (bean instanceof Wild wild) return (String) wild.getParams().get("toto");
            return "age:" + ((Age) bean).getAge();
        } catch (BindException failure) {
            for (Throwable t = failure.getCause(); t != null; t = t.getCause()) {
                if (t instanceof BindValidationException validation) {
                    return "validation:" + validation.getValidationErrors().getAllErrors().stream()
                            .filter(FieldError.class::isInstance).map(FieldError.class::cast)
                            .map(FieldError::getField).sorted().toList().getFirst();
                }
                if (t instanceof IllegalStateException && "'validationType' must not be null".equals(t.getMessage())) {
                    return "unresolved-type";
                }
            }
            throw failure;
        }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> bind("test", Map.of("test.params.toto", "titi"), Wild.class);
            case "control" -> bind("foo", Map.of("foo.age", "4"), Age.class);
            case "challenge" -> bind("test", Map.of("test.params.toto", "titi", "test.age", "9"), Both.class)
                        + "/" + bind("test", Map.of("test.params.toto", "titi", "test.age", "10"), Both.class);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
