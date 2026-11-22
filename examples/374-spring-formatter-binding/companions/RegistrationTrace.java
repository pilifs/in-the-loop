package springwork;

import java.lang.annotation.Annotation;
import java.util.Calendar;
import org.springframework.core.convert.converter.Converter;
import org.springframework.core.convert.converter.ConverterFactory;
import org.springframework.core.convert.converter.GenericConverter;
import org.springframework.format.AnnotationFormatterFactory;
import org.springframework.format.Formatter;
import org.springframework.format.FormatterRegistry;
import org.springframework.format.Parser;
import org.springframework.format.Printer;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.format.datetime.DateFormatter;
import org.springframework.format.datetime.DateFormatterRegistrar;
import org.springframework.format.datetime.DateTimeFormatAnnotationFormatterFactory;

/** Public registry callbacks of the unmodified registrar, in the order they were received. */
public final class RegistrationTrace implements FormatterRegistry {
    private final int[] observed = new int[9];
    private int count;
    private DateFormatter global;
    private static final String[] CONVERTERS = {
        "org.springframework.format.datetime.DateFormatterRegistrar$DateToLongConverter",
        "org.springframework.format.datetime.DateFormatterRegistrar$DateToCalendarConverter",
        "org.springframework.format.datetime.DateFormatterRegistrar$CalendarToDateConverter",
        "org.springframework.format.datetime.DateFormatterRegistrar$CalendarToLongConverter",
        "org.springframework.format.datetime.DateFormatterRegistrar$LongToDateConverter",
        "org.springframework.format.datetime.DateFormatterRegistrar$LongToCalendarConverter"
    };

    private void add(int code) { observed[count++] = code; }

    public void addConverter(Converter<?,?> converter) {
        boolean exact = count < CONVERTERS.length && CONVERTERS[count].equals(converter.getClass().getName());
        add(exact ? count + 1 : -1);
    }
    public void addFormatter(Formatter<?> formatter) { add(formatter == global ? 7 : -1); }
    public void addFormatterForFieldType(Class<?> type, Formatter<?> formatter) {
        add(type == Calendar.class && formatter == global ? 8 : -1);
    }
    public void addFormatterForFieldAnnotation(AnnotationFormatterFactory<? extends Annotation> factory) {
        add(factory.getClass() == DateTimeFormatAnnotationFormatterFactory.class ? 9 : -1);
    }
    public void addPrinter(Printer<?> printer) { add(-1); }
    public void addParser(Parser<?> parser) { add(-1); }
    public void addFormatterForFieldType(Class<?> type, Printer<?> printer, Parser<?> parser) { add(-1); }
    public <S,T> void addConverter(Class<S> source, Class<T> target, Converter<? super S,? extends T> converter) { add(-1); }
    public void addConverter(GenericConverter converter) { add(-1); }
    public void addConverterFactory(ConverterFactory<?,?> factory) { add(-1); }
    public void removeConvertible(Class<?> source, Class<?> target) { add(-1); }

    public static int sequence(int code) {
        var sink = new RegistrationTrace();
        var registrar = new DateFormatterRegistrar();
        if (code == 1) {
            sink.global = new DateFormatter();
            sink.global.setIso(DateTimeFormat.ISO.DATE_TIME);
            registrar.setFormatter(sink.global);
        }
        registrar.registerFormatters(sink);
        if (sink.count != (code == 1 ? 9 : 7)) return -1;
        for (int i = 0; i < 6; i++) if (sink.observed[i] != i+1) return -1;
        int encoded = 0;
        for (int i = 6; i < sink.count; i++) {
            if (sink.observed[i] < 7 || sink.observed[i] > 9) return -1;
            encoded = encoded * 10 + sink.observed[i];
        }
        return encoded;
    }

    public static void main(String[] args) {
        System.out.println(sequence(0));
        System.out.println(sequence(1));
    }
}
