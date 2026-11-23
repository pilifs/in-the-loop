package springwork;

import java.lang.reflect.ParameterizedType;
import org.springframework.core.convert.converter.ConditionalConverter;
import org.springframework.core.convert.converter.ConverterFactory;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.format.support.FormattingConversionService;

/** Return after the first factory supplied by the original setup completes its real registration. */
public final class FirstSignature {
    private static final class Checked extends RuntimeException {}
    private static final class Registry extends FormattingConversionService {
        @Override public void addConverterFactory(ConverterFactory<?, ?> factory) {
            var type = factory.getClass();
            if (!type.getName().equals("org.springframework.core.convert.support.NumberToNumberConverterFactory"))
                throw new AssertionError();
            var interfaces = type.getGenericInterfaces();
            if (interfaces.length != 2 || interfaces[1] != ConditionalConverter.class
                    || !(interfaces[0] instanceof ParameterizedType generic)
                    || generic.getRawType() != ConverterFactory.class || generic.getOwnerType() != null)
                throw new AssertionError();
            var args = generic.getActualTypeArguments();
            if (args.length != 2 || args[0] != Number.class || args[1] != Number.class) throw new AssertionError();
            interfaces[0] = String.class;
            args[1] = String.class;
            if (type.getGenericInterfaces()[0] != generic || generic.getActualTypeArguments()[1] != Number.class)
                throw new AssertionError();
            super.addConverterFactory(factory);
            throw new Checked();
        }
    }

    public static int check() {
        try {
            DefaultConversionService.addDefaultConverters(new Registry());
            return 0;
        } catch (Checked expected) {
            return 1;
        }
    }

    public static void main(String[] args) { System.out.println(check()); }
}
