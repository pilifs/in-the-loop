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
 * A model of {@code java.nio.charset.StandardCharsets} for JBMC: the six charsets every Java platform implementation
 * supports, as instances of the {@link Charset} model, so that a class whose static initializer reads one of them
 * (as {@code public static final Charset DEFAULT = StandardCharsets.UTF_8} does) initializes instead of failing on a
 * stub.
 *
 * @see Charset
 */
public final class StandardCharsets {

    private StandardCharsets() {
        throw new AssertionError("No java.nio.charset.StandardCharsets instances for you!");
    }

    /** Seven-bit ASCII, also known as ISO646-US, also known as the Basic Latin block of the Unicode character set. */
    public static final Charset US_ASCII = new Standard("US-ASCII");

    /** ISO Latin Alphabet No. 1, also known as ISO-LATIN-1. */
    public static final Charset ISO_8859_1 = new Standard("ISO-8859-1");

    /** Eight-bit UCS Transformation Format. */
    public static final Charset UTF_8 = new Standard("UTF-8");

    /** Sixteen-bit UCS Transformation Format, big-endian byte order. */
    public static final Charset UTF_16BE = new Standard("UTF-16BE");

    /** Sixteen-bit UCS Transformation Format, little-endian byte order. */
    public static final Charset UTF_16LE = new Standard("UTF-16LE");

    /** Sixteen-bit UCS Transformation Format, byte order identified by an optional byte-order mark. */
    public static final Charset UTF_16 = new Standard("UTF-16");

    /** A standard charset: a {@link Charset} with nothing but its name. */
    private static final class Standard extends Charset {
        Standard(String canonicalName) {
            super(canonicalName, null);
        }
    }
}
