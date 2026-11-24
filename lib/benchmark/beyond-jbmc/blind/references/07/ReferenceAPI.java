import com.google.auto.common.AnnotationMirrors;
import com.sun.source.util.JavacTask;
import java.net.URI;
import java.util.*;
import javax.lang.model.element.*;
import javax.tools.*;
public final class ReferenceAPI {
    static AnnotationMirror mirror(int n) throws java.io.IOException {
        final String code="@interface Flag {String value() default \"default\";} @Flag"+(n==0?"":"(\"foo\")")+" class Sample {}";
        JavaFileObject file=new SimpleJavaFileObject(URI.create("string:///Sample.java"),JavaFileObject.Kind.SOURCE) {
            public CharSequence getCharContent(boolean ignored) {return code;}
        };
        JavacTask task=(JavacTask)ToolProvider.getSystemJavaCompiler().getTask(null,null,null,Arrays.asList("-proc:none"),null,Arrays.asList(file));
        task.parse();task.analyze();
        return task.getElements().getTypeElement("Sample").getAnnotationMirrors().get(0);
    }
    public static long primary(int n) throws java.io.IOException {
        Map<? extends ExecutableElement,AnnotationValue> values=AnnotationMirrors.getAnnotationValuesWithDefaults(mirror(n));
        if (values.size()!=1) return -1;
        Object x=values.values().iterator().next().getValue();
        return "default".equals(x)?1:"foo".equals(x)?2:0;
    }
    public static long control(int n) throws java.io.IOException {
        Object x=AnnotationMirrors.getAnnotationValue(mirror(n),"value").getValue();
        return (n==0?"default":"foo").equals(x)?1:0;
    }
}
