/*
 * Copyright (c) 2016, 2025, Oracle and/or its affiliates. All rights reserved.
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

import java.util.function.Predicate;
import java.util.function.UnaryOperator;

/**
 * A model of the immutable lists of the JDK's {@code java.util.ImmutableCollections} for JBMC: the lists that
 * {@link List#of} and {@link List#copyOf} return. As in the JDK, a list of one or two elements is a {@code List12},
 * and any other a {@code ListN} over an array of its own (the empty list is one instance, {@code EMPTY_LIST}).
 * Neither holds {@code null}.
 *
 * <p>Kept, as the JDK has them: {@code size}, {@code isEmpty}, {@code get} (an {@code IndexOutOfBoundsException} from
 * a {@code List12}, an {@code ArrayIndexOutOfBoundsException} from a {@code ListN}), {@code indexOf},
 * {@code lastIndexOf} and {@code contains} ({@code NullPointerException} on {@code null}), {@code iterator} (with
 * {@code NoSuchElementException} past the end), {@code toArray()}, {@code equals} and {@code hashCode} over the
 * elements, and every change, {@code add}, {@code set}, {@code remove}, {@code clear}, ..., throwing
 * {@code UnsupportedOperationException}. Left out: exception messages (the JDK's are built by string concatenation,
 * which JBMC stubs), {@code subList}, {@code listIterator}, {@code reversed}, {@code toArray(T[])}, {@code forEach},
 * {@code stream}, {@code toString}, {@code containsAll} and serialization, which stay what JBMC makes of
 * {@code java.util.AbstractCollection}, a stub; and the {@code ListN} that allows {@code null}s, which only
 * {@code Stream.toList} makes. The classes' names are the JDK's, so {@code getClass()} answers as on a JVM; the
 * JDK's {@code AbstractImmutableCollection} is folded into {@code AbstractImmutableList}.
 *
 * <p>No JDK method is called, not even {@code Objects.requireNonNull}, which JBMC would stub: the checks are written
 * out. The interpreter keeps its own natives for these lists, which behave the same (the conformance corpus checks
 * both against a JVM).
 */
final class ImmutableCollections {
    /** The sentinel of a {@code List12}'s unused second element. */
    static final Object EMPTY;

    static final ListN<?> EMPTY_LIST;

    static {
        EMPTY = new Object();
        EMPTY_LIST = new ListN<>(new Object[0]);
    }

    private ImmutableCollections() {
    }

    static UnsupportedOperationException uoe() {
        return new UnsupportedOperationException();
    }

    static <T> T requireNonNull(T o) {
        if (o == null) {
            throw new NullPointerException();
        }
        return o;
    }

    @SuppressWarnings("unchecked")
    static <E> List<E> listCopy(Collection<? extends E> coll) {
        if (coll instanceof List12 || coll instanceof ListN) {
            return (List<E>) coll;
        } else if (coll.isEmpty()) { // the null check of coll
            return List.of();
        } else {
            return (List<E>) List.of(coll.toArray());
        }
    }

    /** A list over a copy of an array the caller keeps: each element checked. */
    @SafeVarargs
    static <E> List<E> listFromArray(E... input) {
        Object[] tmp = new Object[input.length]; // the null check of input
        for (int i = 0; i < input.length; i++) {
            tmp[i] = requireNonNull(input[i]);
        }
        return new ListN<>(tmp);
    }

    /** A list over an array no one else holds (a varargs array): each element checked, the array kept. */
    @SuppressWarnings("unchecked")
    static <E> List<E> listFromTrustedArray(Object... input) {
        for (int i = 0; i < input.length; i++) {
            requireNonNull(input[i]);
        }
        switch (input.length) {
            case 0:
                return (List<E>) EMPTY_LIST;
            case 1:
                return new List12<>((E) input[0]);
            case 2:
                return new List12<>((E) input[0], (E) input[1]);
            default:
                return new ListN<>(input);
        }
    }

    abstract static class AbstractImmutableList<E> extends AbstractCollection<E> implements List<E>, RandomAccess {

        @Override
        public boolean add(E e) {
            throw uoe();
        }

        @Override
        public boolean addAll(Collection<? extends E> c) {
            throw uoe();
        }

        @Override
        public void clear() {
            throw uoe();
        }

        @Override
        public boolean remove(Object o) {
            throw uoe();
        }

        @Override
        public boolean removeAll(Collection<?> c) {
            throw uoe();
        }

        @Override
        public boolean removeIf(Predicate<? super E> filter) {
            throw uoe();
        }

        @Override
        public boolean retainAll(Collection<?> c) {
            throw uoe();
        }

        @Override
        public void add(int index, E element) {
            throw uoe();
        }

        @Override
        public boolean addAll(int index, Collection<? extends E> c) {
            throw uoe();
        }

        @Override
        public E remove(int index) {
            throw uoe();
        }

        @Override
        public E removeFirst() {
            throw uoe();
        }

        @Override
        public E removeLast() {
            throw uoe();
        }

        @Override
        public void replaceAll(UnaryOperator<E> operator) {
            throw uoe();
        }

        @Override
        public E set(int index, E element) {
            throw uoe();
        }

        @Override
        public void sort(Comparator<? super E> c) {
            throw uoe();
        }

        @Override
        public Iterator<E> iterator() {
            return new ListItr<E>(this, size());
        }

        @Override
        public boolean equals(Object o) {
            if (o == this) {
                return true;
            }
            if (!(o instanceof List)) {
                return false;
            }
            Iterator<?> oit = ((List<?>) o).iterator();
            for (int i = 0, s = size(); i < s; i++) {
                if (!oit.hasNext()) {
                    return false;
                }
                // Objects.equals(get(i), oit.next()), with get(i) never null
                Object mine = get(i);
                Object theirs = oit.next();
                if (mine != theirs && !mine.equals(theirs)) {
                    return false;
                }
            }
            return !oit.hasNext();
        }

        @Override
        public int hashCode() {
            int hash = 1;
            for (int i = 0, s = size(); i < s; i++) {
                hash = 31 * hash + get(i).hashCode();
            }
            return hash;
        }

        @Override
        public boolean contains(Object o) {
            return indexOf(o) >= 0;
        }
    }

    static final class ListItr<E> implements Iterator<E> {
        private final AbstractImmutableList<E> list;
        private final int size;
        private int cursor;

        ListItr(AbstractImmutableList<E> list, int size) {
            this.list = list;
            this.size = size;
            this.cursor = 0;
        }

        @Override
        public boolean hasNext() {
            return cursor != size;
        }

        @Override
        public E next() {
            try {
                int i = cursor;
                E next = list.get(i);
                cursor = i + 1;
                return next;
            } catch (IndexOutOfBoundsException e) {
                throw new NoSuchElementException();
            }
        }

        @Override
        public void remove() {
            throw uoe();
        }
    }

    static final class List12<E> extends AbstractImmutableList<E> {
        private final E e0;
        private final Object e1;

        List12(E e0) {
            this.e0 = requireNonNull(e0);
            this.e1 = EMPTY;
        }

        List12(E e0, E e1) {
            this.e0 = requireNonNull(e0);
            this.e1 = requireNonNull(e1);
        }

        @Override
        public int size() {
            return e1 != EMPTY ? 2 : 1;
        }

        @Override
        public boolean isEmpty() {
            return false;
        }

        @Override
        @SuppressWarnings("unchecked")
        public E get(int index) {
            if (index == 0) {
                return e0;
            } else if (index == 1 && e1 != EMPTY) {
                return (E) e1;
            }
            throw new IndexOutOfBoundsException();
        }

        @Override
        public int indexOf(Object o) {
            requireNonNull(o);
            if (o.equals(e0)) {
                return 0;
            } else if (e1 != EMPTY && o.equals(e1)) {
                return 1;
            } else {
                return -1;
            }
        }

        @Override
        public int lastIndexOf(Object o) {
            requireNonNull(o);
            if (e1 != EMPTY && o.equals(e1)) {
                return 1;
            } else if (o.equals(e0)) {
                return 0;
            } else {
                return -1;
            }
        }

        @Override
        public Object[] toArray() {
            if (e1 == EMPTY) {
                return new Object[] { e0 };
            } else {
                return new Object[] { e0, e1 };
            }
        }
    }

    static final class ListN<E> extends AbstractImmutableList<E> {
        private final Object[] elements;

        /** Over {@code elements}, which holds no {@code null} and which no one else changes. */
        ListN(Object[] elements) {
            this.elements = elements;
        }

        @Override
        public boolean isEmpty() {
            return elements.length == 0;
        }

        @Override
        public int size() {
            return elements.length;
        }

        @Override
        @SuppressWarnings("unchecked")
        public E get(int index) {
            return (E) elements[index];
        }

        @Override
        public int indexOf(Object o) {
            if (o == null) {
                throw new NullPointerException();
            }
            Object[] es = elements;
            for (int i = 0; i < es.length; i++) {
                if (o == es[i] || o.equals(es[i])) {
                    return i;
                }
            }
            return -1;
        }

        @Override
        public int lastIndexOf(Object o) {
            if (o == null) {
                throw new NullPointerException();
            }
            Object[] es = elements;
            for (int i = es.length - 1; i >= 0; i--) {
                if (o == es[i] || o.equals(es[i])) {
                    return i;
                }
            }
            return -1;
        }

        @Override
        public Object[] toArray() {
            Object[] copy = new Object[elements.length];
            for (int i = 0; i < elements.length; i++) {
                copy[i] = elements[i];
            }
            return copy;
        }
    }
}
