package org.springframework.data.domain;

/** The sort's shape: `by` and the orders name properties. */
public class Sort {
    public enum Direction { ASC, DESC }

    public static class Order {
        public Order(Direction direction, String property) {}
        public static Order by(String property) { return new Order(Direction.ASC, property); }
        public static Order asc(String property) { return new Order(Direction.ASC, property); }
        public static Order desc(String property) { return new Order(Direction.DESC, property); }
    }

    public static Sort by(String... properties) { return new Sort(); }
    public static Sort by(Direction direction, String... properties) { return new Sort(); }
    public static Sort by(Order... orders) { return new Sort(); }
}
