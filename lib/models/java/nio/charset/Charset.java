/*
 * Copyright (c) 1994, 2013, Oracle and/or its affiliates. All rights reserved.
 * DO NOT ALTER OR REMOVE COPYRIGHT NOTICES OR THIS FILE HEADER.
 *
 * This code is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License version 2 only, as
 * published by the Free Software Foundation.  Oracle designates this
 * particular file as subject to the "Classpath" exception as provided
 * by Oracle in the LICENSE file that accompanied this code.
 *
 * This code is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * version 2 for more details (a copy is included in the LICENSE file that
 * accompanied this code).
 *
 * You should have received a copy of the GNU General Public License version
 * 2 along with this work; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * Please contact Oracle, 500 Oracle Parkway, Redwood Shores, CA 94065 USA
 * or visit www.oracle.com if you need additional information or have any
 * questions.
 */

package java.nio.charset;

/**
 * A model of {@code java.nio.charset.Charset} for JBMC: a named charset without encoders, decoders or providers.
 *
 * <p>The real class resolves charsets through {@code sun.nio.cs} and {@code java.nio.charset.spi}, which JBMC does not
 * model, so a read of {@link StandardCharsets#UTF_8} used to yield a stub object and, under
 * {@code --throw-runtime-exceptions}, a {@code NullPointerException} in the static initializer of any class that reads
 * it (Apache Commons Codec's {@code CharEncoding}, say). This model keeps what programs observe without encoding or
 * decoding: the canonical name, equality by name, ordering, and lookup of the six standard charsets by name.
 *
 * <p>Methods the real class has and this model leaves out ({@code newEncoder}, {@code newDecoder}, {@code encode},
 * {@code decode}, {@code aliases}, {@code availableCharsets}, {@code contains}, {@code canEncode}) stay unmodelled: JBMC
 * treats a call of a missing method as nondeterministic, as it did for the whole class before.
 *
 * @see StandardCharsets
 */
public abstract class Charset implements Comparable<Charset> {

    private final String name;

    /**
     * Initializes a new charset with the given canonical name. The real constructor checks the name's syntax and
     * records the aliases; the model records the name.
     *
     * @param canonicalName the canonical name of this charset
     * @param aliases an array of this charset's aliases, or null if it has no aliases; ignored by the model
     */
    protected Charset(String canonicalName, String[] aliases) {
        this.name = canonicalName;
    }

    /**
     * Tells whether the named charset is one of the six standard charsets. The real method consults every installed
     * provider.
     *
     * @param charsetName the name of the requested charset; may be either a canonical name or an alias
     * @return true if support for the named charset is available
     * @throws IllegalCharsetNameException if the given charset name is null
     */
    public static boolean isSupported(String charsetName) {
        return lookup(charsetName) != null;
    }

    /**
     * Returns a charset object for the named charset: one of the six standard charsets, by canonical name or by the
     * aliases the JDK registers for them.
     *
     * @param charsetName the name of the requested charset; may be either a canonical name or an alias
     * @return a charset object for the named charset
     * @throws IllegalCharsetNameException if the given charset name is null
     * @throws UnsupportedCharsetException if no support for the named charset is available
     */
    public static Charset forName(String charsetName) {
        Charset cs = lookup(charsetName);
        if (cs != null) {
            return cs;
        }
        throw new UnsupportedCharsetException(charsetName);
    }

    /**
     * Returns a charset object for the named charset, or the fallback when none is available.
     *
     * @param charsetName the name of the requested charset
     * @param fallback the fallback charset, returned when the named charset is not available
     * @return a charset object for the named charset, or the fallback
     * @throws IllegalCharsetNameException if the given charset name is null
     * @since 18
     */
    public static Charset forName(String charsetName, Charset fallback) {
        Charset cs = lookup(charsetName);
        return cs != null ? cs : fallback;
    }

    private static Charset lookup(String charsetName) {
        if (charsetName == null) {
            throw new IllegalCharsetNameException(null);
        }
        if (charsetName.equals("UTF-8") || charsetName.equals("UTF8") || charsetName.equals("utf-8") || charsetName.equals("utf8")) {
            return StandardCharsets.UTF_8;
        }
        if (charsetName.equals("US-ASCII") || charsetName.equals("ASCII") || charsetName.equals("us-ascii") || charsetName.equals("ascii")) {
            return StandardCharsets.US_ASCII;
        }
        if (charsetName.equals("ISO-8859-1") || charsetName.equals("ISO8859_1") || charsetName.equals("iso-8859-1") || charsetName.equals("latin1")) {
            return StandardCharsets.ISO_8859_1;
        }
        if (charsetName.equals("UTF-16") || charsetName.equals("UTF16") || charsetName.equals("utf-16")) {
            return StandardCharsets.UTF_16;
        }
        if (charsetName.equals("UTF-16BE") || charsetName.equals("utf-16be")) {
            return StandardCharsets.UTF_16BE;
        }
        if (charsetName.equals("UTF-16LE") || charsetName.equals("utf-16le")) {
            return StandardCharsets.UTF_16LE;
        }
        return null;
    }

    /**
     * Returns the default charset of this Java virtual machine. Since JDK 18 (JEP 400) it is UTF-8 unless the
     * {@code file.encoding} system property says otherwise; the model returns UTF-8.
     *
     * @return the default charset
     */
    public static Charset defaultCharset() {
        return StandardCharsets.UTF_8;
    }

    /**
     * Returns this charset's canonical name.
     *
     * @return the canonical name of this charset
     */
    public final String name() {
        return name;
    }

    /**
     * Returns this charset's human-readable name for the default locale; the model returns the canonical name, as the
     * real class does for the standard charsets.
     *
     * @return the display name of this charset in the default locale
     */
    public String displayName() {
        return name;
    }

    /**
     * Tells whether or not this charset is registered in the IANA Charset Registry. The six standard charsets are.
     *
     * @return true if this charset is known by its implementor to be registered with the IANA
     */
    public final boolean isRegistered() {
        return !name.startsWith("X-") && !name.startsWith("x-");
    }

    /**
     * Compares this charset to another by canonical name, ignoring case.
     *
     * @param that the charset to which this charset is to be compared
     * @return a negative integer, zero, or a positive integer as this charset is less than, equal to, or greater than
     *         the specified charset
     */
    public final int compareTo(Charset that) {
        return name().compareToIgnoreCase(that.name());
    }

    /**
     * Computes a hashcode for this charset: that of its canonical name.
     *
     * @return an integer hashcode
     */
    public final int hashCode() {
        return name().hashCode();
    }

    /**
     * Tells whether or not this object is equal to another: two charsets are equal if they have the same canonical
     * name.
     *
     * @param ob the object to compare with
     * @return true if, and only if, this charset is equal to the given object
     */
    public final boolean equals(Object ob) {
        if (!(ob instanceof Charset)) {
            return false;
        }
        if (this == ob) {
            return true;
        }
        return name.equals(((Charset) ob).name);
    }

    /**
     * Returns a string describing this charset: its canonical name.
     *
     * @return a string describing this charset
     */
    public final String toString() {
        return name();
    }
}
