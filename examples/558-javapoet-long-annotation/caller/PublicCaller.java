import client.Fixtures;

import com.squareup.javapoet.*;

import java.net.*;
import java.nio.file.*;
import java.util.*;

import javax.lang.model.element.Modifier;
import javax.tools.*;

public class PublicCaller {
    public static String observe(String[] a) throws Exception {
        boolean wide = a[0].equals("intent"), many = a[0].equals("challenge");
        var ann =
                wide
                        ? Fixtures.class.getAnnotation(Fixtures.Wide.class)
                        : many
                                ? Fixtures.class.getAnnotation(Fixtures.Many.class)
                                : Fixtures.class.getAnnotation(Fixtures.Small.class);
        var type =
                TypeSpec.classBuilder("Generated")
                        .addModifiers(Modifier.PUBLIC)
                        .addAnnotation(AnnotationSpec.get(ann))
                        .build();
        var file = JavaFile.builder("client.output", type).build();
        Path dest =
                Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")), "classes");
        var compiler = ToolProvider.getSystemJavaCompiler();
        var diagnostics = new DiagnosticCollector<JavaFileObject>();
        boolean success;
        try (var manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, null)) {
            success =
                    compiler.getTask(
                                    null,
                                    manager,
                                    diagnostics,
                                    List.of(
                                            "-proc:none",
                                            "-d",
                                            dest.toString(),
                                            "-classpath",
                                            System.getProperty("java.class.path")),
                                    null,
                                    List.of(file.toJavaFileObject()))
                            .call();
        }
        if (!success
                && diagnostics.getDiagnostics().stream()
                        .noneMatch(d -> d.getCode().equals("compiler.err.int.number.too.large")))
            throw new AssertionError(
                    "unexpected javac diagnostic: " + diagnostics.getDiagnostics());
        String value = "-";
        if (success)
            try (var loader =
                    new URLClassLoader(
                            new URL[] {dest.toUri().toURL()},
                            PublicCaller.class.getClassLoader())) {
                var generated = loader.loadClass("client.output.Generated");
                value =
                        wide
                                ? Long.toString(
                                        generated.getAnnotation(Fixtures.Wide.class).value())
                                : many
                                        ? Arrays.toString(
                                                generated
                                                        .getAnnotation(Fixtures.Many.class)
                                                        .value())
                                        : Integer.toString(
                                                generated
                                                        .getAnnotation(Fixtures.Small.class)
                                                        .value());
            }
        return (wide ? file.toString().contains("12345678910L") + "/" : "") + success + "/" + value;
    }
}
