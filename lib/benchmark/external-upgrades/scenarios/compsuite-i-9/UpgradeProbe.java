package org.languagetool.dev.wikipedia.atom;

import java.util.Date;
import java.util.List;
import org.languagetool.Language;
import org.languagetool.Languages;
import org.languagetool.rules.Category;
import org.languagetool.rules.CategoryId;
import org.languagetool.rules.RuleMatch;

public final class UpgradeProbe {
    private static WikipediaRuleMatch match(Language language, int ruleId, long diff, long millis) {
        FakeRule rule = new FakeRule(ruleId);
        rule.setCategory(new Category(new CategoryId("TEST_ID"), "My Category"));
        RuleMatch match = new RuleMatch(rule, null, 5, 10, "my message");
        AtomFeedItem item = new AtomFeedItem("//id?diff=" + diff, "title", "summary", new Date(millis));
        return new WikipediaRuleMatch(language, match, "my context", item);
    }

    public static String observe(String[] input) throws Exception {
        Language language = Languages.getLanguageForShortCode("de");
        MatchDatabase database = new MatchDatabase("jdbc:derby:atomFeedChecksDB;create=true", "user", "pass");
        database.createTables();
        database.add(match(language, 1, 123, 10000));
        int updated = database.markedFixed(match(language, input[0].equals("same") ? 1 : 2, 124, 9000000000L));
        List<StoredWikipediaRuleMatch> rows = database.list();
        StoredWikipediaRuleMatch row = rows.get(0);
        return rows.size() + "/" + row.getRuleId() + "/" + row.getDiffId() + "/" + updated + "/" + row.getFixDiffId();
    }
}
