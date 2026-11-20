package styles;
import java.util.Iterator;
import java.util.ServiceLoader;
import styleapi.Construction;
import styleapi.PageStyle;

public final class Lookup {
    public static String[] inspect() {
        Construction.log = "";
        ServiceLoader<PageStyle> services = ServiceLoader.load(PageStyle.class, Thread.currentThread().getContextClassLoader());
        String created = Construction.log;
        Iterator<PageStyle> iterator = services.iterator();
        boolean present = iterator.hasNext();
        String looked = Construction.log;
        String first = present ? iterator.next().name() : "";
        String firstConstructed = Construction.log;
        String order = first;
        while (iterator.hasNext()) order += iterator.next().name();
        return new String[]{order, first, created, looked, firstConstructed, Construction.log};
    }
}
