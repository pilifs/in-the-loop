package springwork;

import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import org.springframework.core.ResolvableType;
import org.springframework.core.convert.converter.ConditionalConverter;
import org.springframework.core.convert.converter.ConverterFactory;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.format.support.FormattingConversionService;

/** Observe the first factory the original default-converter setup actually submits. */
public final class ConverterInterfaces {
    private static final class Registered extends RuntimeException {}

    private static final class Registry extends FormattingConversionService {
        @Override public void addConverterFactory(ConverterFactory<?, ?> factory) {
            var type = factory.getClass();
            Type[] interfaces = type.getGenericInterfaces();
            if (interfaces.length != 2 || !(interfaces[0] instanceof ParameterizedType generic)
                    || generic.getRawType() != ConverterFactory.class || generic.getOwnerType() != null
                    || interfaces[1] != ConditionalConverter.class) throw new AssertionError();
            Type[] arguments = generic.getActualTypeArguments();
            if (arguments.length != 2 || arguments[0] != Number.class || arguments[1] != Number.class) throw new AssertionError();
            var resolved = ResolvableType.forClass(type).as(ConverterFactory.class).getGenerics();
            if (resolved.length != 2 || resolved[0].resolve() != Number.class || resolved[1].resolve() != Number.class)
                throw new AssertionError();
            super.addConverterFactory(factory);
            System.out.println(type.getName());
            System.out.println(interfaces[0].getTypeName());
            System.out.println(interfaces[1].getTypeName());
            System.out.println(resolved[0].resolve().getName() + " " + resolved[1].resolve().getName() + " registered");
            throw new Registered();
        }
    }

    public static void main(String[] args) {
        try {
            DefaultConversionService.addDefaultConverters(new Registry());
            throw new AssertionError("no converter factory registered");
        } catch (Registered expected) {}
    }
}
