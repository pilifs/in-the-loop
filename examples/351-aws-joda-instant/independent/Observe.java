package com.amazonaws.util;

import java.util.Date;
import org.joda.time.DateTime;

public final class Observe {
    public static void main(String[] args) {
        for (long millis : new long[]{Long.MAX_VALUE, 946684800123L}) {
            String printed = DateUtils.iso8601DateFormat.print(millis);
            try {
                DateTime parsed = DateUtils.iso8601DateFormat.parseDateTime(printed);
                System.out.println("formatter\t" + millis + "\t" + printed + "\treturn\t" + parsed.getMillis());
            } catch (IllegalArgumentException error) {
                System.out.println("formatter\t" + millis + "\t" + printed + "\tthrow\t"
                        + error.getClass().getName() + "\t" + error.getMessage());
            }
            String publicText = DateUtils.formatISO8601Date(new Date(millis));
            try {
                System.out.println("sdk\t" + millis + "\t" + publicText + "\treturn\t"
                        + DateUtils.parseISO8601Date(publicText).getTime());
            } catch (RuntimeException error) {
                System.out.println("sdk\t" + millis + "\t" + publicText + "\tthrow\t" + error.getClass().getName());
            }
        }
    }
}
