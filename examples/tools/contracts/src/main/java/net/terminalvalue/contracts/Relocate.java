package net.terminalvalue.contracts;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;

/**
 * Copies a directory of compiled classes into a new package prefix, so that two versions of the same classes can be
 * loaded side by side: {@code net.example.Pricing} becomes {@code before.net.example.Pricing}, and every reference
 * between the copied classes follows.
 *
 * <p>Class names only ever appear in a class file's constant pool, as UTF-8 entries: on their own (class entries), inside
 * field and method descriptors ({@code Lnet/example/Pricing;}), and inside generic signatures ({@code
 * Lnet/example/Pricing<...>;}). Rewriting those entries, and nothing else, relocates the class. Everything after the
 * constant pool refers to entries by index and is copied unchanged.
 */
final class Relocate {

    private Relocate() {}

    /** Copies every class under {@code in} to {@code out/<prefix>/...}, renamed. Returns the relocated class names. */
    static Set<String> directory(Path in, Path out, String prefix) throws IOException {
        List<Path> files;
        try (Stream<Path> walk = Files.walk(in)) {
            files = walk.filter(p -> p.toString().endsWith(".class")).toList();
        }
        Set<String> own = new HashSet<>();
        for (Path file : files) {
            own.add(in.relativize(file).toString().replace('\\', '/').replaceAll("\\.class$", ""));
        }
        for (Path file : files) {
            Path target = out.resolve(prefix).resolve(in.relativize(file).toString());
            Files.createDirectories(target.getParent());
            Files.write(target, classFile(Files.readAllBytes(file), own, prefix));
        }
        return own;
    }

    static byte[] classFile(byte[] bytes, Set<String> own, String prefix) throws IOException {
        var in = new DataInputStream(new java.io.ByteArrayInputStream(bytes));
        var buffer = new ByteArrayOutputStream(bytes.length + 256);
        var out = new DataOutputStream(buffer);
        out.writeInt(in.readInt()); // magic
        out.writeShort(in.readUnsignedShort()); // minor
        out.writeShort(in.readUnsignedShort()); // major
        int count = in.readUnsignedShort();
        out.writeShort(count);
        for (int i = 1; i < count; i++) {
            int tag = in.readUnsignedByte();
            out.writeByte(tag);
            switch (tag) {
                case 1 -> out.writeUTF(rename(in.readUTF(), own, prefix)); // Utf8
                case 3, 4 -> out.writeInt(in.readInt()); // Integer, Float
                case 5, 6 -> { // Long, Double take two slots
                    out.writeLong(in.readLong());
                    i++;
                }
                case 7, 8, 16, 19, 20 -> out.writeShort(in.readUnsignedShort()); // Class, String, MethodType, Module, Package
                case 9, 10, 11, 12, 17, 18 -> { // Fieldref, Methodref, InterfaceMethodref, NameAndType, Dynamic, InvokeDynamic
                    out.writeShort(in.readUnsignedShort());
                    out.writeShort(in.readUnsignedShort());
                }
                case 15 -> { // MethodHandle
                    out.writeByte(in.readUnsignedByte());
                    out.writeShort(in.readUnsignedShort());
                }
                default -> throw new IOException("unknown constant pool tag " + tag);
            }
        }
        in.transferTo(out);
        return buffer.toByteArray();
    }

    /** Renames a constant pool string if it is a relocated class name or contains one as a descriptor. */
    static String rename(String s, Set<String> own, String prefix) {
        if (own.contains(s)) {
            return prefix + "/" + s;
        }
        if (s.indexOf('L') < 0) {
            return s;
        }
        var result = new StringBuilder();
        int i = 0;
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c == 'L') {
                int end = i + 1;
                while (end < s.length() && s.charAt(end) != ';' && s.charAt(end) != '<') {
                    end++;
                }
                String name = s.substring(i + 1, end);
                if (own.contains(name)) {
                    result.append('L').append(prefix).append('/').append(name);
                    i = end;
                    continue;
                }
            }
            result.append(c);
            i++;
        }
        return result.toString();
    }
}
