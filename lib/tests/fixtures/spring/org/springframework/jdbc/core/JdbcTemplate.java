// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the class and its methods, which are the real ones.
package org.springframework.jdbc.core;

public class JdbcTemplate {
    public int update(String sql, Object... args) { return 0; }
    public <T> T queryForObject(String sql, Class<T> type, Object... args) { return null; }
}
