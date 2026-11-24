import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.parser.Parser;
import org.jsoup.parser.Tag;

public class UpgradeProbe {
    public static String observe(String[] args) {
        String name = args[0];
        Parser original = Parser.htmlParser();
        original.tagSet().add(new Tag("foo").set(Tag.Void));
        int[] callbackCount = {0};
        original.tagSet().onNewTag(tag -> {
            if (tag.normalName().equals("fresh")) {
                callbackCount[0]++;
                tag.set(Tag.Void);
            }
        });
        Parser clone = original.clone();
        if (clone.tagSet() == original.tagSet() || clone.tagSet().get("late", Parser.NamespaceHtml) != null)
            throw new AssertionError("the clone must have its own set before registration");
        original.tagSet().add(new Tag("late").set(Tag.Void));
        Tag existing = clone.tagSet().get(name, Parser.NamespaceHtml);
        if (existing != null && existing == original.tagSet().get(name, Parser.NamespaceHtml))
            throw new AssertionError("a tag copied from the source must be distinct");
        StringBuilder history = new StringBuilder().append(existing != null);
        for (int i = 0; i < 2; i++) {
            Document doc = clone.parseInput("<" + name + ">one<span>two</span>after", "");
            Element first = doc.expectFirst(name);
            Element span = doc.expectFirst("span");
            history.append('|').append(first.tag().isEmpty()).append('/').append(span.parent().tagName())
                    .append('/').append(first.text()).append('/').append(doc.text()).append('/').append(callbackCount[0]);
        }
        return history.toString();
    }
}
