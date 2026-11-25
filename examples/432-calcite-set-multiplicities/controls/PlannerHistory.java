import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import org.apache.calcite.plan.RelOptListener;
import org.apache.calcite.plan.RelOptPlanner;
import org.apache.calcite.rel.RelNode;
import org.apache.calcite.rel.core.SetOp;
import org.apache.calcite.rel.rules.ProjectSetOpTransposeRule;
import org.apache.calcite.runtime.Hook;
import org.apache.calcite.util.JsonBuilder;

/** Observe the planner around the unchanged JDBC caller. Each query also returns its actual rows. */
public class PlannerHistory implements RelOptListener {
    private final Map<String, Integer> attempts = new TreeMap<>();
    private final Map<String, Integer> productions = new TreeMap<>();
    private final List<String> converted = new ArrayList<>();
    private final List<String> trimmed = new ArrayList<>();
    private int planners;
    private boolean otherRulesAttempted;

    private static String shape(RelNode node) {
        if (node.getInputs().isEmpty()) return node.getRelTypeName();
        return node.getRelTypeName() + node.getInputs().stream().map(PlannerHistory::shape)
                .collect(Collectors.joining(",", "(", ")"));
    }

    @Override public void ruleAttempted(RuleAttemptedEvent event) {
        if (!event.isBefore()) return;
        var call = event.getRuleCall();
        if (call.getRule() instanceof ProjectSetOpTransposeRule) {
            attempts.merge(((SetOp) call.rel(1)).kind.name(), 1, Integer::sum);
        } else {
            otherRulesAttempted = true;
        }
    }

    @Override public void ruleProductionSucceeded(RuleProductionEvent event) {
        if (!event.isBefore()) return;
        var call = event.getRuleCall();
        if (call.getRule() instanceof ProjectSetOpTransposeRule) {
            productions.merge(((SetOp) call.rel(1)).kind.name(), 1, Integer::sum);
        }
    }

    @Override public void relEquivalenceFound(RelEquivalenceEvent event) {}
    @Override public void relDiscarded(RelDiscardedEvent event) {}
    @Override public void relChosen(RelChosenEvent event) {}

    public static String observe(String[] args) throws Exception {
        var listener = new PlannerHistory();
        try (var planner = Hook.PLANNER.addThread((Consumer<RelOptPlanner>) p -> {
                 p.addListener(listener);
                 listener.planners++;
             });
             var converted = Hook.CONVERTED.addThread((Consumer<RelNode>) r -> listener.converted.add(shape(r)));
             var trimmed = Hook.TRIMMED.addThread((Consumer<RelNode>) r -> listener.trimmed.add(shape(r)))) {
            var result = new LinkedHashMap<String, Object>();
            result.put("publicReturn", PublicCaller.observe(args));
            result.put("planners", listener.planners);
            result.put("converted", listener.converted);
            result.put("trimmed", listener.trimmed);
            result.put("otherRulesAttempted", listener.otherRulesAttempted);
            result.put("transposeAttempts", listener.attempts);
            result.put("transposeProductions", listener.productions);
            return new JsonBuilder().toJsonString(result);
        }
    }
}
