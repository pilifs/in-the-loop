import org.springframework.beans.factory.*;
import org.springframework.beans.factory.support.*;
import org.springframework.core.ParameterizedTypeReference;

import java.lang.reflect.InvocationTargetException;

public class PublicCaller {
    public static class Box<T> {
        public T value;
    }

    public static class TextBox extends Box<String> {
        public TextBox() {
            value = "text";
        }
    }

    public static class CountBox extends Box<Number> {
        public CountBox() {
            value = 42;
        }
    }

    static final ParameterizedTypeReference<Box<String>> TEXT =
            new ParameterizedTypeReference<>() {};
    static final ParameterizedTypeReference<Box<Number>> COUNT =
            new ParameterizedTypeReference<>() {};

    static String fields(BeanNotOfRequiredTypeException failure) {
        return failure.getBeanName()
                + ":"
                + failure.getRequiredType().getSimpleName()
                + ":"
                + TEXT.getType().equals(failure.getGenericRequiredType())
                + ":"
                + failure.getActualType().getSimpleName();
    }

    public static String observe(String[] args) throws Exception {
        var factory = new DefaultListableBeanFactory();
        factory.registerBeanDefinition("text", new RootBeanDefinition(TextBox.class));
        factory.registerBeanDefinition("count", new RootBeanDefinition(CountBox.class));
        Object text = factory.getBean("text"), count = factory.getBean("count");
        if (args[0].equals("raw")) {
            String selected =
                    (factory.getBean("count", Box.class) == count ? "count" : "other")
                            + "/"
                            + (factory.getBean("text") == text ? "text" : "other");
            try {
                factory.getBean("absent");
                return selected + "/found";
            } catch (NoSuchBeanDefinitionException e) {
                return selected + "/" + e.getClass().getSimpleName();
            }
        }
        boolean exact;
        try {
            BeanFactory.class.getMethod("getBean", String.class, ParameterizedTypeReference.class);
            exact = true;
        } catch (NoSuchMethodException e) {
            exact = false;
        }
        if (args[0].equals("java") && !exact) return "absent";
        String javaFailure = "accepted";
        if (exact) {
            if (factory.getBean("text", TEXT) != text) return "wrong singleton";
            try {
                factory.getBean("count", TEXT);
            } catch (BeanNotOfRequiredTypeException e) {
                javaFailure = fields(e);
            }
        }
        if (args[0].equals("java")) return "text/" + javaFailure;
        Class<?> kotlin = Class.forName("KotlinCallsKt");
        String kotlinResult;
        try {
            kotlinResult =
                    kotlin.getMethod("asText", BeanFactory.class).invoke(null, factory) == count
                            ? "count"
                            : "other";
        } catch (InvocationTargetException e) {
            kotlinResult = fields((BeanNotOfRequiredTypeException) e.getCause());
        }
        if (!exact) return "kotlin=" + kotlinResult;
        return "java="
                + javaFailure
                + " kotlin="
                + kotlinResult
                + " success="
                + (factory.getBean("count", COUNT) == count)
                + "/"
                + (kotlin.getMethod("asNumber", BeanFactory.class).invoke(null, factory) == count);
    }
}
