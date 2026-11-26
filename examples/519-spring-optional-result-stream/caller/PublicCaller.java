import org.springframework.dao.IncorrectResultSizeDataAccessException;
import org.springframework.dao.support.DataAccessUtils;

import java.util.*;
import java.util.function.*;
import java.util.stream.*;

public class PublicCaller {
    static final Object MARK = new Object();

    static String call(Supplier<?> action) {
        try {
            Object value = action.get();
            if (value instanceof Optional<?> opt)
                return opt.isEmpty() ? "empty" : opt.get() == MARK ? "identical" : "other";
            return value == null ? "null" : value == MARK ? "identical" : "other";
        } catch (IncorrectResultSizeDataAccessException e) {
            return "too-many(" + e.getExpectedSize() + ")";
        }
    }

    static String cardinality(int kind) {
        List<String> answers = new ArrayList<>();
        for (List<Object> input : List.of(List.<Object>of(), List.of(MARK), List.of(MARK, MARK))) {
            answers.add(
                    call(
                            () ->
                                    switch (kind) {
                                        case 0 -> DataAccessUtils.optionalResult(input);
                                        case 1 -> DataAccessUtils.optionalResult(input.iterator());
                                        case 2 -> DataAccessUtils.optionalResult(input.stream());
                                        default -> DataAccessUtils.singleResult(input);
                                    }));
        }
        return String.join(",", answers);
    }

    public static String observe(String[] args) {
        if (args[0].equals("old")) return cardinality(3);
        try {
            if (args[0].equals("cardinality"))
                return cardinality(0) + " / " + cardinality(1) + " / " + cardinality(2);
            int[] read = {0}, closed = {0}, singleton = {0};
            Stream<Object> two =
                    Stream.generate(
                                    () -> {
                                        if (++read[0] > 2)
                                            throw new AssertionError("third element requested");
                                        return MARK;
                                    })
                            .onClose(() -> closed[0]++);
            String error = call(() -> DataAccessUtils.optionalResult(two));
            String one =
                    call(
                            () ->
                                    DataAccessUtils.optionalResult(
                                            Stream.of(MARK).onClose(() -> singleton[0]++)));
            return error
                    + ":read="
                    + read[0]
                    + ":closed="
                    + closed[0]
                    + " / "
                    + one
                    + ":closed="
                    + singleton[0];
        } catch (NoSuchMethodError unavailable) {
            return "absent";
        }
    }
}
