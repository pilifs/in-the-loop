import java.lang.reflect.UndeclaredThrowableException;
import org.aopalliance.intercept.MethodInterceptor;
import org.springframework.aop.framework.ProxyFactory;
import static org.mockito.Mockito.*;

public class PublicCaller {
    public static class DeclaredProblem extends Exception {}
    public static class OtherProblem extends Exception {}
    public interface Operation {void act() throws DeclaredProblem;}
    public static class Target implements Operation {public void act() throws DeclaredProblem {}}
    record Seen(Throwable advice,Throwable caller,int handlers) {}
    static Seen invoke(boolean classProxy, Throwable problem, boolean handle) throws DeclaredProblem {
        var target=mock(Target.class);
        doAnswer(inv -> {throw problem;}).when(target).act();
        var factory=new ProxyFactory(target);
        factory.setInterfaces(Operation.class);
        factory.setProxyTargetClass(classProxy);
        Throwable[] advice={null}; int[] handlers={0};
        factory.addAdvice((MethodInterceptor)call -> {
            try {return call.proceed();}
            catch(OtherProblem e) {advice[0]=e; if(handle) {handlers[0]++; return null;} throw e;}
            catch(Throwable ex) {advice[0]=ex; throw ex;}
        });
        var proxy=(Operation)factory.getProxy();
        Throwable caught=null;
        try {proxy.act();} catch(Throwable e) {caught=e;}
        return new Seen(advice[0],caught,handlers[0]);
    }
    static String kind(Throwable t,Throwable marker) {
        if(t==null) return "normal";
        return t==marker ? "original" : t instanceof UndeclaredThrowableException ? "wrapper" : t.getClass().getSimpleName();
    }
    static boolean allowed(boolean classProxy) throws Exception {
        for(Throwable e:new Throwable[]{new DeclaredProblem(),new IllegalStateException()}) {
            var seen=invoke(classProxy,e,false);
            if(seen.advice()!=e || seen.caller()!=e) return false;
        }
        return true;
    }
    public static String observe(String[] args) throws Exception {
        var marker=new OtherProblem();
        if(args[0].equals("allowed")) {
            var jdk=invoke(false,marker,false);
            return "class="+allowed(true)+" jdk="+allowed(false)+" jdkUndeclared="+(jdk.advice()==marker
                    && jdk.caller() instanceof UndeclaredThrowableException && jdk.caller().getCause()==marker);
        }
        if(args[0].equals("recover")) {
            var a=invoke(true,marker,true); var b=invoke(false,marker,true);
            return "class="+kind(a.caller(),marker)+":"+a.handlers()+" jdk="+kind(b.caller(),marker)+":"+b.handlers();
        }
        var seen=invoke(true,marker,false);
        return "advice="+kind(seen.advice(),marker)+" caller="+kind(seen.caller(),marker)
                +" cause="+(seen.caller()!=null && seen.caller().getCause()==marker);
    }
}
