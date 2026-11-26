import java.time.LocalDate;
import java.util.Optional;
import org.springframework.core.ResolvableType;
import org.springframework.core.convert.ConversionException;
import org.springframework.core.convert.TypeDescriptor;
import org.springframework.core.convert.support.DefaultConversionService;

public class PublicCaller {
    public static String observe(String[] args) {
        var service = new DefaultConversionService();
        var type = ResolvableType.forClassWithGenerics(Optional.class, Integer.class);
        var source = new TypeDescriptor(type, Optional.class, null);
        var date = TypeDescriptor.valueOf(LocalDate.class);
        var target = args[0].equals("string") ? TypeDescriptor.valueOf(String.class) : date;
        if (args[0].equals("converter")) {
            service.addConverter(Integer.class, LocalDate.class, i -> LocalDate.ofEpochDay(i));
        }
        String result = "eligible=" + service.canConvert(source, target);
        try {
            Object value = service.convert(Optional.of(42), source, target);
            result += " " + value.getClass().getSimpleName() + "=" + value;
        } catch (ConversionException e) {
            result += " error=" + e.getClass().getSimpleName();
        }
        if (args[0].equals("string")) result += " raw=" + service.canConvert(TypeDescriptor.valueOf(Optional.class), date);
        return result;
    }
}
