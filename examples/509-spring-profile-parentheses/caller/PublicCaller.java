import org.springframework.context.annotation.*;
import org.springframework.core.env.*;

public class PublicCaller {
    @Profile("dev)")
    static class Malformed {}

    @Profile("dev")
    static class Valid {}

    static String parse(StandardEnvironment env, String expression) {
        Profiles profiles;
        try {
            profiles = Profiles.of(expression);
        } catch (IllegalArgumentException e) {
            return e.getClass().getSimpleName();
        }
        return String.valueOf(env.acceptsProfiles(profiles));
    }

    static String register(Class<?> bean) {
        try (var context = new AnnotationConfigApplicationContext()) {
            context.getEnvironment().setActiveProfiles("dev");
            context.register(bean);
            context.refresh();
            return context.getBean(bean) != null ? "loaded" : "missing";
        } catch (RuntimeException failure) {
            for (Throwable e = failure; e != null; e = e.getCause()) {
                if (e instanceof IllegalArgumentException && e.getMessage().contains("profile"))
                    return "malformed";
            }
            throw failure;
        }
    }

    public static String observe(String[] args) {
        StandardEnvironment env = new StandardEnvironment();
        env.setActiveProfiles("dev");
        if (args[0].equals("parse")) return parse(env, "dev)") + "/" + parse(env, "(dev");
        if (args[0].equals("annotation"))
            return register(Malformed.class) + "/" + register(Valid.class);
        Profiles valid = Profiles.of("(dev & !prod)");
        boolean first = env.acceptsProfiles(valid);
        env.setActiveProfiles("dev", "prod");
        return first + "/" + env.acceptsProfiles(valid);
    }
}
