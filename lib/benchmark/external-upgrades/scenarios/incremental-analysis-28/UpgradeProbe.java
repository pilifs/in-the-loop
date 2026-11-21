package com.worksap.tools.spotbugs.maven.incremental;

import java.nio.file.*;
import java.util.Base64;
import java.util.stream.*;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Path root = Paths.get("output");
        Path pkg = root.resolve("evaluation/fixture");
        Files.createDirectories(pkg);
        Files.write(pkg.resolve("Empty.class"), Base64.getDecoder().decode(args[0]));
        Files.write(pkg.resolve("Numbers.class"), Base64.getDecoder().decode(args[1]));
        ClassSearcher finder = new ClassSearcher(root);
        return finder.search(Stream.of("evaluation/fixture/" + args[2] + ".java"))
                .sorted().collect(Collectors.joining(","));
    }
}
