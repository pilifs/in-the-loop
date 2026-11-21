package com.iodesystems.whatjdk;

import java.io.*;
import java.util.*;
import java.util.zip.*;
import org.objectweb.asm.*;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream out = new ZipOutputStream(buffer)) {
            out.putNextEntry(new ZipEntry("input.class"));
            out.write(Base64.getDecoder().decode(args[0]));
        }
        ClassEntryExtractor reader = new ClassEntryExtractor("input.jar",
                new ZipInputStream(new ByteArrayInputStream(buffer.toByteArray())));
        ClassEntry entry = reader.next();
        List<String> declarations = new ArrayList<>();
        entry.getClassReader().accept(new ClassVisitor(Opcodes.ASM6) {
            public void visit(int version, int access, String name, String signature, String parent, String[] interfaces) {
                declarations.add("C " + version + " " + access + " " + name + " " + parent + " " + String.join(",", interfaces));
            }
            public FieldVisitor visitField(int access, String name, String desc, String signature, Object value) {
                declarations.add("F " + access + " " + name + " " + desc);
                return null;
            }
            public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                declarations.add("M " + access + " " + name + " " + desc);
                return null;
            }
        }, ClassReader.SKIP_CODE | ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        return String.join("\n", declarations);
    }
}
