package claims;

import java.beans.PropertyChangeSupport;
import java.beans.VetoableChangeSupport;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;
import java.util.Collections;
import java.util.EventListener;
import java.util.Iterator;
import java.util.Spliterator;
import java.util.Spliterators;
import javax.swing.event.EventListenerList;

public final class ReaderAndListeners {
    interface Notice extends EventListener { }
    static final class One implements Notice {
        public boolean equals(Object other) { return this == other; }
    }

    public static boolean chars(boolean shifted) throws IOException {
        int cp = shifted ? 0x1F600 : 0x10FFFF;
        byte[] emoji = {(byte) 0xf0, (byte) 0x9f, (byte) 0x98, (byte) 0x80};
        var utf8 = java.nio.charset.StandardCharsets.UTF_8;
        if (!new String(emoji, utf8).equals("\uD83D\uDE00")
                || !new String(emoji, 0, 3, utf8).equals("\uFFFD")
                || !new String(emoji, 1, 2, utf8).equals("\uFFFD\uFFFD")) return false;
        if (!Character.isSupplementaryCodePoint(cp) || Character.isSupplementaryCodePoint(0xFEFF)
                || !Character.isSurrogate(Character.highSurrogate(cp)) || !Character.isSurrogate(Character.lowSurrogate(cp))
                || Character.highSurrogate(cp) != (shifted ? 0xD83D : 0xDBFF)
                || Character.lowSurrogate(cp) != (shifted ? 0xDE00 : 0xDFFF) || Character.isSurrogate('\uFEFF')) return false;
        String text = "a\ud800b";
        char[] out = {'x', 'x', 'x', 'x'};
        int offset = shifted ? 1 : 0;
        text.getChars(1, 3, out, offset);
        if (out[offset] != '\ud800' || out[offset + 1] != 'b' || out[3] != 'x') return false;
        StringReader r = new StringReader(text);
        if (r.read() != 'a') return false;
        r.mark(4);
        if (r.read(out, 1, 3) != 2 || out[1] != '\ud800' || out[2] != 'b' || out[3] != 'x' || r.read() != -1) return false;
        r.reset();
        if (r.read() != '\ud800' || r.skip(1) != 1 || r.read(out, 0, 0) != 0) return false;
        r.close();
        try { r.read(); return false; } catch (IOException expected) { return true; }
    }

    public static boolean buffered() throws IOException {
        byte[] bytes = {3, (byte) 255, 9};
        java.io.ByteArrayInputStream source = new java.io.ByteArrayInputStream(bytes);
        if (source.read() != 3) return false;
        source.mark(2);
        if (source.read() != 255) return false;
        source.reset();
        bytes[1] = 7;
        if (source.read() != 7 || source.read() != 9 || source.read() != -1) return false;
        byte[] copy = {3, 7, 9};
        if (!java.util.Arrays.equals(bytes, copy) || java.util.Arrays.equals(bytes, (byte[]) null)) return false;
        copy[2] = -1;
        if (java.util.Arrays.equals(bytes, copy) || java.util.Arrays.equals(bytes, new byte[]{3, 7})) return false;
        try (Reader r = new BufferedReader(new StringReader("a\udfffz"), 2)) {
            return r.read() == 'a' && r.read() == '\udfff' && r.read() == 'z' && r.read() == -1;
        }
    }

    public static boolean listeners(boolean twice) {
        EventListenerList l = new EventListenerList();
        One first = new One(), second = new One();
        if (!Notice.class.isInstance(first) || Notice.class.isInstance(null) || Notice.class.isInstance("x")) return false;
        l.add(Notice.class, null);
        l.add(Notice.class, first);
        Object[] original = l.getListenerList();
        l.add(Notice.class, twice ? first : second);
        if (l.getListenerCount(Notice.class) != 2 || original == l.getListenerList()) return false;
        l.remove(Notice.class, first);
        Object[] rest = l.getListenerList();
        return original.length == 2 && original[0] == Notice.class && original[1] == first
                && rest.length == 2 && rest[0] == Notice.class && rest[1] == (twice ? first : second);
    }

    public static boolean mirrors() {
        char[] copy = "xy".toCharArray();
        copy[0] = 'z';
        return "xy".charAt(0) == 'x' && copy != "xy".toCharArray()
                && int.class != Integer.class && int.class == int[].class.getComponentType() && void.class == Void.TYPE
                && int.class.isPrimitive() && !Integer.class.isPrimitive() && !int.class.isInstance(Integer.valueOf(2))
                && int.class.isAssignableFrom(int.class) && !int.class.isAssignableFrom(long.class)
                && !Object.class.isAssignableFrom(int.class) && Boolean.TYPE.getClassLoader() == null;
    }

    public static boolean beans() {
        Object source = new Object();
        if (new PropertyChangeSupport(source).hasListeners("x") || new VetoableChangeSupport(source).hasListeners("x")) return false;
        try { new PropertyChangeSupport(null); return false; } catch (NullPointerException expected) { return true; }
    }

    public static boolean cursor() {
        if (Collections.emptyList() != Collections.EMPTY_LIST || !Collections.emptyList().isEmpty()) return false;
        Iterator<String> it = new Iterator<String>() {
            boolean read;
            public boolean hasNext() { return !read; }
            public String next() { read = true; return "x"; }
        };
        Spliterator<String> split = Spliterators.spliteratorUnknownSize(it, Spliterator.ORDERED);
        String[] seen = new String[1];
        return split.characteristics() == Spliterator.ORDERED && split.tryAdvance(x -> seen[0] = x)
                && "x".equals(seen[0]) && !split.tryAdvance(x -> seen[0] = "y") && !it.hasNext();
    }

    public static boolean wrong() throws IOException { return new StringReader("ab").read() == 'b'; }
    public static boolean propertyChanges(boolean choose) {
        String key = "test.reader.paper";
        System.clearProperty(key);
        String selected = choose ? "Letter" : "A4";
        if (System.getProperty(key, "A4") != "A4" || System.setProperty(key, selected) != null) return false;
        return System.getProperty(key) == selected && System.clearProperty(key) == selected
                && System.getProperty(key) == null;
    }
    public static boolean nestedLock() {
        var lock = new java.util.concurrent.locks.ReentrantLock();
        lock.lock();
        if (!lock.tryLock() || !lock.isHeldByCurrentThread() || lock.getHoldCount() != 2) return false;
        lock.unlock();
        lock.unlock();
        return !lock.isLocked();
    }
    public static boolean unknownProperty() { return System.getProperty("test.reader.initial") == null; }
    public static boolean invalidRange() { "ab".getChars(0, 2, new char[1], 0); return true; }
    public static void main(String[] args) throws IOException {
        if (!chars(true) || !chars(false) || !buffered() || !listeners(true) || !listeners(false) || !mirrors() || !beans() || !cursor() || !propertyChanges(true) || !propertyChanges(false) || !nestedLock() || wrong()) throw new AssertionError();
    }
}
