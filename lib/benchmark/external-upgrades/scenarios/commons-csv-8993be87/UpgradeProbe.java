package org.apache.commons.csv;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        try (CSVParser parser = CSVParser.parse(args[0], CSVFormat.DEFAULT)) {
            StringBuilder out = new StringBuilder();
            CSVRecord row;
            while ((row = parser.nextRecord()) != null) {
                if (out.length() != 0) out.append('|');
                out.append('[');
                for (String field : row) out.append(field.length()).append(':').append(field);
                out.append(']');
            }
            return out.toString();
        }
    }
}
