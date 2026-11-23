package springwork;

import org.springframework.core.convert.converter.Converter;
import org.springframework.core.convert.converter.ConverterFactory;
import org.springframework.core.convert.converter.GenericConverter;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.format.support.FormattingConversionService;

public final class ScalarPrefix {
    private static final class PrefixComplete extends RuntimeException {}

    private static final class Registry extends FormattingConversionService {
        int completed;
        final boolean firstTwo;

        Registry(boolean firstTwo) { this.firstTwo = firstTwo; }

        @Override public void addConverter(GenericConverter converter) {
            super.addConverter(converter);
            completed++;
        }

        @Override public void addConverter(Converter<?, ?> converter) {
            if (converter.getClass().getName().equals("org.springframework.core.convert.support.EnumToStringConverter"))
                throw new PrefixComplete();
            super.addConverter(converter);
        }

        @Override public void addConverterFactory(ConverterFactory<?, ?> factory) {
            if (firstTwo) {
                String expected = completed == 0 ? "org.springframework.core.convert.support.NumberToNumberConverterFactory"
                    : "org.springframework.core.convert.support.StringToNumberConverterFactory";
                if (!expected.equals(factory.getClass().getName())) throw new AssertionError();
            }
            super.addConverterFactory(factory);
            if (firstTwo && completed == 2) throw new PrefixComplete();
        }
    }

    public static int check() {
        return prefix(true, 2);
    }

    private static int prefix(boolean firstTwo, int expected) {
        var registry = new Registry(firstTwo);
        try {
            DefaultConversionService.addDefaultConverters(registry);
            return 0;
        } catch (PrefixComplete finished) {
            return registry.completed == expected ? 1 : 0;
        }
    }

    public static void main(String[] args) { System.out.println(check() + " " + prefix(false, 10)); }
}
