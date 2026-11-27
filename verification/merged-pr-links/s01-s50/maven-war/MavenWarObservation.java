package org.springframework.boot.maven;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.jar.JarFile;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(MavenBuildExtension.class)
class MavenWarObservation {
    @TestTemplate
    void readSingleSbom(MavenBuild build) { measure(build, false); }

    @TestTemplate
    void readWithEarlierDecoy(MavenBuild build) { measure(build, true); }

    private static void measure(MavenBuild build, boolean decoy) {
        String marker = "{\"fixture\":\"original\"}";
        String sbom = "WEB-INF/classes/META-INF/sbom/application.cdx.json";
        String other = "WEB-INF/classes/other/application.cdx.json";
        build.project("verified-sbom").goals("org.apache.maven.plugins:maven-war-plugin:3.5.1:war",
                "fixture:war-order:1:decoy-first",
                "org.springframework.boot:spring-boot-maven-plugin:repackage")
                .prepare(project -> {
                    Path dir = project.toPath();
                    Path classes = Files.createDirectories(dir.resolve("target/classes"));
                    Path source = dir.resolve("Main.java");
                    Files.writeString(source, "package fixture; public class Main { public static void main(String[] args) {} }");
                    if (ToolProvider.getSystemJavaCompiler().run(null,null,null,"-proc:none","-d",classes.toString(),source.toString()) != 0)
                        throw new IllegalStateException("fixture did not compile");
                    Path payload = classes.resolve("META-INF/sbom/application.cdx.json");
                    Files.createDirectories(payload.getParent());
                    Files.writeString(payload,marker);
                    Path web = Files.createDirectories(dir.resolve("src/main/webapp"));
                    Files.createDirectories(web.resolve("WEB-INF"));
                    Files.writeString(web.resolve("WEB-INF/web.xml"), "<web-app xmlns=\"https://jakarta.ee/xml/ns/jakartaee\" version=\"6.0\"/>");
                    if (decoy) {
                        Files.createDirectories(classes.resolve("other"));
                        Files.writeString(classes.resolve("other/application.cdx.json"),"{\"fixture\":\"other\"}");
                    }
                }).execute(project -> {
                    Path target = project.toPath().resolve("target/fixture-1.war");
                    try (JarFile archive = new JarFile(target.toFile())) {
                        var attributes = archive.getManifest().getMainAttributes();
                        String format = attributes.getValue("Sbom-Format");
                        String location = attributes.getValue("Sbom-Location");
                        String selected = location == null ? "absent" :
                                new String(archive.getInputStream(archive.getJarEntry(location)).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
                        if (!marker.equals(new String(archive.getInputStream(archive.getJarEntry(sbom)).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)))
                            throw new IllegalStateException("missing original Maven WAR payload");
                        List<String> entries = Collections.list(archive.entries()).stream().map(e -> e.getName()).toList();
                        if (decoy && archive.getJarEntry(other) == null) throw new IllegalStateException("missing second WAR payload");
                        String outputOrder = decoy ? Boolean.toString(entries.indexOf(other) < entries.indexOf(sbom)) : "single";
                        String inputOrder;
                        try (JarFile original = new JarFile(target.toString() + ".original")) {
                            List<String> input = Collections.list(original.entries()).stream().map(e -> e.getName()).toList();
                            inputOrder = decoy ? Boolean.toString(input.indexOf(other) >= 0 && input.indexOf(other) < input.indexOf(sbom)) : "single";
                            if (decoy && !Boolean.parseBoolean(inputOrder))
                                throw new IllegalStateException("decoy did not precede the selected resource at Maven repackage");
                        }
                        Path out = Path.of(System.getenv("BOOT_S48_RECEIPTS"),UUID.randomUUID() + ".txt");
                        Files.write(out,List.of(decoy ? "challenge" : "intent",String.valueOf(format),String.valueOf(location),selected,inputOrder,outputOrder));
                    }
                });
    }
}
