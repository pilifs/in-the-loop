package fixture;

import java.io.File;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.apache.maven.plugin.AbstractMojo;
import org.apache.maven.plugin.MojoExecutionException;

/** Places the second fixture resource first in the input of the subsequent Boot goal. */
public class WarOrderMojo extends AbstractMojo {
    private File war;
    @Override public void execute() throws MojoExecutionException {
        String decoy = "WEB-INF/classes/other/application.cdx.json";
        String selected = "WEB-INF/classes/META-INF/sbom/application.cdx.json";
        Path ordered = war.toPath().resolveSibling(war.getName() + ".ordered");
        try {
            try (ZipFile source = new ZipFile(war)) {
                if (source.getEntry(selected) == null) throw new IllegalStateException("Maven WAR omitted fixture SBOM");
                if (source.getEntry(decoy) == null) return;
                var entries = Collections.list(source.entries());
                entries.sort(Comparator.comparing(e -> !e.getName().equals(decoy)));
                try (var out = new ZipOutputStream(Files.newOutputStream(ordered))) {
                    for (var entry : entries) {
                        var next = new ZipEntry(entry.getName());
                        next.setTime(entry.getTime());
                        next.setMethod(entry.getMethod());
                        if (next.getMethod() == ZipEntry.STORED) { next.setSize(entry.getSize()); next.setCrc(entry.getCrc()); }
                        out.putNextEntry(next);
                        try (var in = source.getInputStream(entry)) { in.transferTo(out); }
                        out.closeEntry();
                    }
                }
            }
            Files.move(ordered,war.toPath(),StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception ex) { throw new MojoExecutionException("could not order the fixture WAR",ex); }
    }
}
