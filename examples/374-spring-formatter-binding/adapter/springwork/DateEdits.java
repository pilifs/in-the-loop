package springwork;

import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import org.springframework.beans.MutablePropertyValues;
import org.springframework.context.i18n.LocaleContextHolder;
import org.springframework.context.i18n.SimpleTimeZoneAwareLocaleContext;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.format.datetime.DateFormatter;
import org.springframework.format.datetime.DateFormatterRegistrar;
import org.springframework.format.support.FormattingConversionService;
import org.springframework.validation.DataBinder;

public final class DateEdits {
    public static final String LOCAL = "10/31/09 1:05", BAD = "bad-date";
    public static final String GLOBAL = "2009-10-31T01:05:00.000Z";
    public static final long MILLIS = 1256951100000L;

    public static final class Bean {
        @DateTimeFormat(pattern="M/d/yy h:mm") private Date local;
        private Date global;
        public Date getLocal() { return local; }
        public Date getGlobal() { return global; }
        public void setLocal(Date value) { local = value; }
        public void setGlobal(Date value) { global = value; }
    }
    public record Prefix(Long millis, int errors, String field, Object rejected, Object displayed) {
        public Object[] values() { return new Object[]{millis,errors,field,rejected,displayed}; }
    }

    public static Prefix[] history(int mode) {
        var original = LocaleContextHolder.getLocaleContext();
        var zone = TimeZone.getTimeZone("UTC");
        LocaleContextHolder.setLocaleContext(new SimpleTimeZoneAwareLocaleContext(Locale.US,zone));
        try {
            DateFormatter formatter = new DateFormatter();
            formatter.setIso(DateTimeFormat.ISO.DATE_TIME);
            formatter.setTimeZone(zone);
            DateFormatterRegistrar registrar = new DateFormatterRegistrar();
            registrar.setFormatter(formatter);
            var service = new FormattingConversionService();
            DefaultConversionService.addDefaultConverters(service);
            registrar.registerFormatters(service);
            Bean bean = new Bean();
            var binder = new DataBinder(bean);
            binder.setConversionService(service);
            Prefix[] result = new Prefix[mode == 3 ? 2 : 1];
            String key = mode == 1 ? "global" : "local";
            for (int i = 0; i < result.length; i++) {
                String text = mode == 1 ? GLOBAL : mode >= 2 && i == 0 ? BAD : LOCAL;
                binder.bind(new MutablePropertyValues().add(key,text));
                var ledger = binder.getBindingResult();
                var error = ledger.getFieldError();
                Date value = mode == 1 ? bean.getGlobal() : bean.getLocal();
                result[i] = new Prefix(value == null ? null : value.getTime(),ledger.getErrorCount(),
                    error == null ? null : error.getField(),error == null ? null : error.getRejectedValue(),ledger.getFieldValue(key));
            }
            return result;
        } finally { LocaleContextHolder.setLocaleContext(original); }
    }

    static boolean matches(Prefix row, boolean stored, int errors, String rejected, String shown) {
        return (stored ? row.millis != null && row.millis.longValue() == MILLIS : row.millis == null)
                && row.errors == errors && (errors == 0 ? row.field == null && row.rejected == null
                : "local".equals(row.field) && rejected.equals(row.rejected)) && shown.equals(row.displayed);
    }
    public static int annotated(int code) {
        Prefix[] h = history(code == 0 ? 0 : 3);
        return (code == 0 ? matches(h[0],true,0,null,LOCAL)
                : matches(h[0],false,1,BAD,BAD) && matches(h[1],true,1,BAD,BAD)) ? 1 : 0;
    }
    public static int preservation(int code) {
        Prefix p = history(code == 0 ? 1 : 2)[0];
        return (code == 0 ? matches(p,true,0,null,GLOBAL) : matches(p,false,1,BAD,BAD)) ? 1 : 0;
    }
}
