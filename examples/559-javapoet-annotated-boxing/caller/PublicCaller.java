import com.squareup.javapoet.*;

import java.util.*;

public class PublicCaller {
    static AnnotationSpec ann(String s) {
        return AnnotationSpec.builder(ClassName.get("fixture", s)).build();
    }

    static List<String> names(TypeName t) {
        return t.annotations.stream().map(a -> ((ClassName) a.type).simpleName()).toList();
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge")) {
            var initial = ClassName.get("java.lang", "Integer").annotated(ann("A"), ann("B"));
            var primitive = initial.unbox();
            var boxed = primitive.box();
            return primitive.withoutAnnotations()
                    + "/"
                    + names(primitive)
                    + "/"
                    + boxed.withoutAnnotations()
                    + "/"
                    + names(boxed)
                    + "/"
                    + initial.equals(boxed);
        }
        var initial =
                a[0].equals("control") ? TypeName.BOOLEAN : TypeName.BOOLEAN.annotated(ann("A"));
        var w = initial.box();
        var p = w.unbox();
        if (a[0].equals("control"))
            return w + "/" + w.isBoxedPrimitive() + "/" + (p == TypeName.BOOLEAN) + "/" + names(p);
        return w.withoutAnnotations()
                + "/"
                + names(w)
                + "/"
                + w.isBoxedPrimitive()
                + "/"
                + p.withoutAnnotations()
                + "/"
                + names(p)
                + "/"
                + initial.equals(p);
    }
}
