import java.lang.reflect.*;
import java.sql.*;
import java.util.*;
import org.springframework.jdbc.datasource.AbstractDataSource;
import org.springframework.jdbc.support.DatabaseStartupValidator;

public class PublicCaller {
    static <T> T proxy(Class<T> type, InvocationHandler handler) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(),new Class<?>[]{type},handler));
    }
    static class Loans extends AbstractDataSource {
        final List<String> calls=new ArrayList<>();
        final String mode;
        int acquired;
        boolean firstClosed;
        Loans(String mode) { this.mode=mode; }
        public Connection getConnection(String u,String p) { return getConnection(); }
        public Connection getConnection() {
            String id=String.valueOf((char)('A'+acquired++));
            calls.add("open"+id);
            return proxy(Connection.class,(self,m,args) -> {
                switch (m.getName()) {
                    case "isValid":
                        calls.add("valid"+id+"("+args[0]+")");
                        if (mode.equals("query")) throw new AssertionError("unexpected validity check");
                        if (id.equals("B") && !firstClosed) throw new AssertionError("A still loaned");
                        if (id.equals("A") && mode.equals("throws")) throw new SQLException("transient");
                        return !id.equals("A") || !mode.equals("false");
                    case "createStatement":
                        calls.add("statement"+id);
                        return proxy(Statement.class,(s,method,a) -> {
                            if (method.getName().equals("execute")) { calls.add((String)a[0]); return true; }
                            if (method.getName().equals("close")) { calls.add("closeStatement"+id); return null; }
                            throw new AssertionError(method);
                        });
                    case "close": calls.add("close"+id); if (id.equals("A")) firstClosed=true; return null;
                    case "toString": return "loan"+id;
                    default: throw new AssertionError(m);
                }
            });
        }
    }
    static String run(String mode) {
        var ds=new Loans(mode);
        var check=new DatabaseStartupValidator();
        check.setDataSource(ds); check.setInterval(1); check.setTimeout(6);
        if (mode.equals("query")) check.setValidationQuery("SELECT 1");
        String result="ok";
        try { check.afterPropertiesSet(); } catch (RuntimeException e) { result=e.getClass().getSimpleName(); }
        return result + " " + ds.calls;
    }
    public static String observe(String[] args) {
        return args[0].equals("retry") ? run("false") + " / " + run("throws") : run(args[0]);
    }
}
