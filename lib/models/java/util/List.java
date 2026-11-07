/*
 * Copyright (c) 1997, 2025, Oracle and/or its affiliates. All rights reserved.
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

package java.util;

/**
 * A model of the static factories of the JDK's {@code java.util.List} for JBMC, which has no bytecode for them and
 * stubbed each as a method that returns any list, or {@code null}. The factories are the JDK's, step for step: they
 * return the lists of {@link ImmutableCollections}, throw {@code NullPointerException} on a {@code null} element (or
 * array, or collection), and {@code copyOf} hands back the list itself when it is already one of them.
 *
 * <p>The interface declares, besides {@code Collection}'s, the instance methods the model's lists define, as
 * abstract methods, so that a call of one resolves here as on a JVM. Left out: {@code listIterator},
 * {@code subList}, {@code reversed}, {@code spliterator}, {@code getFirst}, {@code getLast}, {@code addFirst} and
 * {@code addLast}, which stay JBMC's stubs; and {@code java.util.Collection}, which stays JBMC's own. On a list
 * that is not one of the model's (an {@code ArrayList}, say, which JBMC has no bytecode for either), a call is
 * JBMC's stub, as before.
 *
 * <p>The interpreter keeps its own natives for these factories, which behave the same (the conformance corpus checks
 * both against a JVM).
 */
public interface List<E> extends Collection<E> {

    E get(int index);

    E set(int index, E element);

    void add(int index, E element);

    E remove(int index);

    boolean addAll(int index, Collection<? extends E> c);

    int indexOf(Object o);

    int lastIndexOf(Object o);

    void replaceAll(java.util.function.UnaryOperator<E> operator);

    void sort(Comparator<? super E> c);

    E removeFirst();

    E removeLast();

    @SuppressWarnings("unchecked")
    static <E> List<E> of() {
        return (List<E>) ImmutableCollections.EMPTY_LIST;
    }

    static <E> List<E> of(E e1) {
        return new ImmutableCollections.List12<>(e1);
    }

    static <E> List<E> of(E e1, E e2) {
        return new ImmutableCollections.List12<>(e1, e2);
    }

    static <E> List<E> of(E e1, E e2, E e3) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5, E e6) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5, e6);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5, E e6, E e7) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5, e6, e7);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5, E e6, E e7, E e8) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5, e6, e7, e8);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5, E e6, E e7, E e8, E e9) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5, e6, e7, e8, e9);
    }

    static <E> List<E> of(E e1, E e2, E e3, E e4, E e5, E e6, E e7, E e8, E e9, E e10) {
        return ImmutableCollections.listFromTrustedArray(e1, e2, e3, e4, e5, e6, e7, e8, e9, e10);
    }

    @SafeVarargs
    @SuppressWarnings("unchecked")
    static <E> List<E> of(E... elements) {
        switch (elements.length) { // the null check of elements
            case 0:
                return (List<E>) ImmutableCollections.EMPTY_LIST;
            case 1:
                return new ImmutableCollections.List12<>(elements[0]);
            case 2:
                return new ImmutableCollections.List12<>(elements[0], elements[1]);
            default:
                return ImmutableCollections.listFromArray(elements);
        }
    }

    static <E> List<E> copyOf(Collection<? extends E> coll) {
        return ImmutableCollections.listCopy(coll);
    }
}
