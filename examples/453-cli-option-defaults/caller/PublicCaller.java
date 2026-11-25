import java.util.Arrays;
import java.util.Properties;
import org.apache.commons.cli.CommandLine;
import org.apache.commons.cli.DefaultParser;
import org.apache.commons.cli.MissingOptionException;
import org.apache.commons.cli.Option;
import org.apache.commons.cli.Options;
import org.apache.commons.cli.ParseException;

public class PublicCaller {
    static Options options(boolean required) {
        Options options = new Options().addOption(Option.builder("o").hasArg().get());
        if (required) options.addOption(Option.builder("r").required().get());
        return options;
    }

    static CommandLine parse(DefaultParser parser, Options options, String value, String... argv)
            throws ParseException {
        Properties properties = new Properties();
        properties.setProperty("o", value);
        return parser.parse(options, argv, properties);
    }

    static String stored(Options options) {
        return Arrays.toString(options.getOption("o").getValues());
    }

    static String retry(Options options) throws ParseException {
        CommandLine result = parse(new DefaultParser(), options, "retry", "-r");
        return result.getOptionValue("o") + "/" + result.hasOption("r") + "/" + result.getArgList();
    }

    public static String observe(String[] args) throws ParseException {
        DefaultParser parser = new DefaultParser();
        switch (args[0]) {
        case "reuse":
            Options shared = options(false);
            CommandLine first = parse(parser, shared, "first");
            String initial = "first=" + first.getOptionValue("o") + " stored1=" + stored(shared);
            CommandLine second = parse(parser, shared, "second");
            return initial + " second=" + second.getOptionValue("o") + " retained=" + first.getOptionValue("o")
                    + " stored2=" + stored(shared);
        case "preset":
            Option option = Option.builder("o").hasArg().get();
            option.getValuesList().add("preset");
            Options preset = new Options().addOption(option);
            return "value=" + parse(parser, preset, "fallback").getOptionValue("o") + " stored=" + stored(preset);
        case "retry":
            Options required = options(true);
            String status;
            try {
                status = "returned:" + parse(parser, required, "discarded").getOptionValue("o");
            } catch (MissingOptionException e) {
                status = e.getClass().getSimpleName() + e.getMissingOptions();
            }
            return "first=" + status + " retry=" + retry(required) + " fresh=" + retry(options(true));
        default:
            throw new IllegalArgumentException(args[0]);
        }
    }
}
