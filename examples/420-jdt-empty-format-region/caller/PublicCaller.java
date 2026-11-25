import java.util.*;
import org.eclipse.jdt.core.JavaCore;
import org.eclipse.jdt.core.ToolFactory;
import org.eclipse.jdt.core.formatter.*;
import org.eclipse.jface.text.*;
import org.eclipse.text.edits.TextEdit;

public class PublicCaller {
    static String apply(CodeFormatter formatter, String source, String sep, String selection) throws Exception {
        var empty = new Region(0, 0);
        var real = new Region(sep.length(), source.length() - sep.length());
        IRegion[] regions = switch (selection) {
            case "real" -> new IRegion[]{real};
            case "empty" -> new IRegion[]{empty};
            default -> new IRegion[]{empty, real};
        };
        TextEdit edit = formatter.format(CodeFormatter.K_COMPILATION_UNIT, source, regions, 0, sep);
        if (edit == null) throw new IllegalStateException("formatter returned null");
        var doc = new Document(source);
        edit.apply(doc);
        return doc.get();
    }
    public static String observe(String[] args) throws Exception {
        Map<String,String> options = DefaultCodeFormatterConstants.getEclipseDefaultSettings();
        options.put(JavaCore.COMPILER_SOURCE, JavaCore.VERSION_17);
        options.put(JavaCore.COMPILER_COMPLIANCE, JavaCore.VERSION_17);
        options.put(JavaCore.COMPILER_CODEGEN_TARGET_PLATFORM, JavaCore.VERSION_17);
        var formatter = ToolFactory.createCodeFormatter(options, ToolFactory.M_FORMAT_EXISTING);
        String sep = args[0].equals("crlf") ? "\r\n" : "\n";
        String original = sep + "class A{void foo(){int x=1;}}" + sep;
        if (args[0].equals("separate"))
            return "real=" + apply(formatter, original, sep, "real") + "empty=" + apply(formatter, original, sep, "empty");
        String result = apply(formatter, original, sep, "both");
        if (args[0].equals("crlf")) return result + "; idempotent=" + result.equals(apply(formatter, result, sep, "both"));
        return result;
    }
}
