import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.lang.reflect.WildcardType;
import org.springframework.core.convert.converter.Converter;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.format.support.FormattingConversionService;
import springwork.DateEdits;

public final class FormatterBinding {
    static final class Found extends RuntimeException {}
    static final class Registry extends FormattingConversionService {
        boolean intact;
        @Override public void addConverter(Converter<?,?> converter) {
            super.addConverter(converter);
            Class<?> klass=converter.getClass();
            if (!klass.getName().equals("org.springframework.core.convert.support.EnumToStringConverter")) return;
            Type[] types=klass.getGenericInterfaces();
            if (types.length==1 && types[0] instanceof ParameterizedType) {
                ParameterizedType signature=(ParameterizedType)types[0];
                Type[] args=signature.getActualTypeArguments();
                if (signature.getRawType()==Converter.class && args.length==2 && args[1]==String.class
                    && args[0] instanceof ParameterizedType) {
                    ParameterizedType e=(ParameterizedType)args[0];
                    Type w=e.getActualTypeArguments()[0];
                    intact=e.getRawType()==Enum.class && w instanceof WildcardType
                        && ((WildcardType)w).getUpperBounds()[0]==Object.class;
                }
            }
            throw new Found();
        }
    }
    public static boolean registeredEnum() {
        Registry registry=new Registry();
        try {DefaultConversionService.addDefaultConverters(registry);return false;}
        catch (Found exact) {return registry.intact;}
    }
    public static boolean annotated(int mode) {return mode<0 || mode>1 || DateEdits.annotated(mode)==1;}
    public static boolean preservation(int mode) {return mode<0 || mode>1 || DateEdits.preservation(mode)==1;}
}
