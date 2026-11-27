import com.sun.source.tree.*;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import javax.lang.model.element.*;
import javax.lang.model.type.*;
import javax.lang.model.util.Elements;
import javax.lang.model.util.Types;
import javax.tools.*;

/** Evaluator-only source analysis. Parse the preserved caller; never load or execute its application. */
public final class ReferenceFacts extends TreePathScanner<Void, Map<String, Object>> {
    private static final Object UNKNOWN = new Object();
    private final Trees trees;
    private final Types types;
    private final Elements elements;
    private final String[] arguments;
    private final Set<ExecutableElement> active = new HashSet<>();
    private final Set<String> fixtureOwners = new HashSet<>();
    private final List<String> rows = new ArrayList<>();
    private int possibleBranches;
    private int nextHandle;
    private record Handle(int index, boolean constructed) {}

    private ReferenceFacts(JavacTask compiler, String[] args) {
        trees = Trees.instance(compiler);
        types = compiler.getTypes();
        elements = compiler.getElements();
        arguments = args;
    }

    private String descriptor(TypeMirror type) {
        switch (type.getKind()) {
            case BOOLEAN: return "Z";
            case BYTE: return "B";
            case CHAR: return "C";
            case SHORT: return "S";
            case INT: return "I";
            case LONG: return "J";
            case FLOAT: return "F";
            case DOUBLE: return "D";
            case VOID: return "V";
            case ARRAY: return "[" + descriptor(((ArrayType) type).getComponentType());
            default:
                Element element = types.asElement(types.erasure(type));
                return element instanceof TypeElement t ? "L" + elements.getBinaryName(t).toString().replace('.', '/') + ";" : "?";
        }
    }

    private Object literal(ExpressionTree expression, Map<String, Object> values) {
        if (expression instanceof ParenthesizedTree t) return literal(t.getExpression(), values);
        if (expression instanceof LiteralTree t) return t.getValue();
        if (expression instanceof IdentifierTree t) return values.getOrDefault(t.getName().toString(), UNKNOWN);
        if (expression instanceof ArrayAccessTree t && t.getExpression() instanceof IdentifierTree id
                && values.get(id.getName().toString()) == arguments && literal(t.getIndex(), values) instanceof Integer i
                && i >= 0 && i < arguments.length) return arguments[i];
        if (expression instanceof UnaryTree t && t.getKind() == Tree.Kind.LOGICAL_COMPLEMENT) {
            Object v = literal(t.getExpression(), values);
            return v instanceof Boolean ? !(Boolean) v : UNKNOWN;
        }
        if (expression instanceof BinaryTree t && (t.getKind() == Tree.Kind.EQUAL_TO || t.getKind() == Tree.Kind.NOT_EQUAL_TO)) {
            Object a = literal(t.getLeftOperand(), values), b = literal(t.getRightOperand(), values);
            if (a != UNKNOWN && b != UNKNOWN) return Objects.equals(a, b) == (t.getKind() == Tree.Kind.EQUAL_TO);
        }
        if (expression instanceof MethodInvocationTree t && t.getMethodSelect() instanceof MemberSelectTree m
                && m.getIdentifier().contentEquals("equals") && t.getArguments().size() == 1) {
            Object a = literal(m.getExpression(), values), b = literal(t.getArguments().get(0), values);
            if (a != UNKNOWN && b != UNKNOWN) return Objects.equals(a, b);
        }
        return UNKNOWN;
    }

    private void row(String... values) {
        if (rows.size() >= 2048) throw new IllegalStateException("reference fact budget exhausted");
        StringJoiner fields = new StringJoiner("\t");
        for (String value : values) fields.add(Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));
        rows.add(fields.toString());
    }

    private static String handle(Object value) {
        return value instanceof Handle h ? (h.constructed() ? "constructed-" : "object-") + h.index() : "";
    }

    private void called(List<? extends ExpressionTree> args, ExpressionTree receiver, Map<String, Object> values) {
        Element element = trees.getElement(getCurrentPath());
        if (!(element instanceof ExecutableElement method) || !(method.getEnclosingElement() instanceof TypeElement owner)) return;
        String cls = elements.getBinaryName(owner).toString();
        TreePath implementation = trees.getPath(method);
        if (fixtureOwners.contains(cls.split("\\$")[0]) && implementation != null && implementation.getLeaf() instanceof MethodTree body) {
            if (body.getBody() != null && active.add(method)) {
                Map<String, Object> local = new HashMap<>();
                for (int i = 0; i < Math.min(args.size(), method.getParameters().size()); i++)
                    local.put(method.getParameters().get(i).getSimpleName().toString(), literal(args.get(i), values));
                scan(new TreePath(implementation, body.getBody()), local);
                active.remove(method);
            }
            return;
        }
        if (!method.getModifiers().contains(Modifier.PUBLIC)) return;
        StringBuilder signature = new StringBuilder(cls).append('#').append(method.getSimpleName()).append('(');
        for (VariableElement parameter : method.getParameters()) signature.append(descriptor(types.erasure(parameter.asType())));
        signature.append(')').append(descriptor(types.erasure(method.getReturnType())));
        String selector = signature.toString();
        Object result = UNKNOWN;
        if (getCurrentPath().getParentPath().getLeaf() instanceof VariableTree v)
            result = values.getOrDefault(v.getName().toString(), UNKNOWN);
        List<String> argumentHandles = new ArrayList<>();
        for (int i = 0; i < args.size(); i++)
            if (literal(args.get(i), values) instanceof Handle h) argumentHandles.add(i + "=" + handle(h));
        row("action", selector, method.getReturnType().toString(), possibleBranches == 0 ? "on selected source branch" : "conditional source branch",
                handle(literal(receiver, values)), handle(result), String.join(",", argumentHandles));
        for (int i = 0; i < Math.min(args.size(), method.getParameters().size()); i++) {
            Object value = literal(args.get(i), values);
            if (value == UNKNOWN || value == arguments || value instanceof Handle) continue;
            String typ = method.getParameters().get(i).asType().toString();
            row("argument", selector, Integer.toString(i), typ, Objects.toString(value, "null"));
        }
    }

    @Override public Void visitMethodInvocation(MethodInvocationTree t, Map<String, Object> v) {
        scan(t.getMethodSelect(), v);
        scan(t.getArguments(), v);
        called(t.getArguments(), t.getMethodSelect() instanceof MemberSelectTree s ? s.getExpression() : null, v);
        return null;
    }
    @Override public Void visitNewClass(NewClassTree t, Map<String, Object> v) {
        scan(t.getArguments(), v);
        called(t.getArguments(), null, v);
        return null;
    }
    @Override public Void visitVariable(VariableTree t, Map<String, Object> values) {
        Object value = literal(t.getInitializer(), values);
        Element variable = trees.getElement(getCurrentPath());
        if (value == UNKNOWN && variable != null && !variable.asType().getKind().isPrimitive())
            value = new Handle(++nextHandle, t.getInitializer() instanceof NewClassTree);
        values.put(t.getName().toString(), value);
        scan(t.getInitializer(), values);
        return null;
    }
    @Override public Void visitIf(IfTree t, Map<String, Object> v) {
        Object condition = literal(t.getCondition(), v);
        if (condition instanceof Boolean result) {
            scan(result ? t.getThenStatement() : t.getElseStatement(), v);
        } else {
            scan(t.getCondition(), v);
            possibleBranches++;
            scan(t.getThenStatement(), new HashMap<>(v));
            scan(t.getElseStatement(), new HashMap<>(v));
            possibleBranches--;
        }
        return null;
    }
    @Override public Void visitConditionalExpression(ConditionalExpressionTree t, Map<String, Object> v) {
        Object condition = literal(t.getCondition(), v);
        if (condition instanceof Boolean b) return scan(b ? t.getTrueExpression() : t.getFalseExpression(), v);
        possibleBranches++;
        super.visitConditionalExpression(t, v);
        possibleBranches--;
        return null;
    }
    @Override public Void visitTry(TryTree t, Map<String, Object> v) {
        scan(t.getResources(), v);
        scan(t.getBlock(), v);
        possibleBranches++;
        scan(t.getCatches(), new HashMap<>(v));
        possibleBranches--;
        scan(t.getFinallyBlock(), v);
        return null;
    }
    @Override public Void visitForLoop(ForLoopTree t, Map<String, Object> v) {
        scan(t.getInitializer(), v);
        scan(t.getCondition(), v);
        possibleBranches++;
        scan(t.getStatement(), v);
        scan(t.getUpdate(), v);
        possibleBranches--;
        return null;
    }
    @Override public Void visitEnhancedForLoop(EnhancedForLoopTree t, Map<String, Object> v) {
        scan(t.getExpression(), v);
        possibleBranches++;
        scan(t.getStatement(), new HashMap<>(v));
        possibleBranches--;
        return null;
    }
    @Override public Void visitWhileLoop(WhileLoopTree t, Map<String, Object> v) {
        scan(t.getCondition(), v);
        possibleBranches++;
        scan(t.getStatement(), new HashMap<>(v));
        possibleBranches--;
        return null;
    }
    private boolean terminal(StatementTree s, Map<String, Object> v) {
        if (s instanceof ReturnTree || s instanceof ThrowTree) return true;
        if (s instanceof BlockTree b) return b.getStatements().stream().anyMatch(t -> terminal(t, v));
        if (s instanceof IfTree t && literal(t.getCondition(), v) instanceof Boolean b)
            return terminal(b ? t.getThenStatement() : t.getElseStatement(), v);
        return false;
    }
    @Override public Void visitBlock(BlockTree t, Map<String, Object> v) {
        for (StatementTree statement : t.getStatements()) {
            scan(statement, v);
            if (terminal(statement, v)) break;
        }
        return null;
    }
    private void alternatives(ExpressionTree subject, List<? extends CaseTree> cases, Map<String, Object> v) {
        Object discriminator = literal(subject, v);
        if (discriminator == UNKNOWN) {
            possibleBranches++;
            scan(cases, new HashMap<>(v));
            possibleBranches--;
            return;
        }
        CaseTree otherwise = null;
        for (CaseTree c : cases) {
            if (c.getExpressions().isEmpty()) otherwise = c;
            if (c.getExpressions().stream().anyMatch(label -> Objects.equals(literal(label, v), discriminator))) {
                scan(c, v);
                return;
            }
        }
        scan(otherwise, v);
    }
    @Override public Void visitSwitch(SwitchTree t, Map<String, Object> v) {
        alternatives(t.getExpression(), t.getCases(), v); return null;
    }
    @Override public Void visitSwitchExpression(SwitchExpressionTree t, Map<String, Object> v) {
        alternatives(t.getExpression(), t.getCases(), v); return null;
    }
    @Override public Void visitCase(CaseTree t, Map<String, Object> v) {
        if (t.getBody() != null) scan(t.getBody(), v); else scan(t.getStatements(), v);
        return null;
    }

    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        List<String> files = Files.readAllLines(root.resolve("source-files"));
        String[] arguments = Files.readAllLines(root.resolve("arguments")).stream()
                .map(s -> new String(Base64.getDecoder().decode(s), StandardCharsets.UTF_8)).toArray(String[]::new);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager fm = compiler.getStandardFileManager(diagnostics, null, StandardCharsets.UTF_8)) {
            List<String> options = List.of("-proc:none", "--class-path", Files.readString(root.resolve("classpath")));
            JavacTask task = (JavacTask) compiler.getTask(null, fm, diagnostics, options, null, fm.getJavaFileObjectsFromStrings(files));
            List<CompilationUnitTree> units = new ArrayList<>();
            task.parse().forEach(units::add);
            task.analyze();
            ReferenceFacts scanner = new ReferenceFacts(task, arguments);
            for (CompilationUnitTree unit : units) for (Tree tree : unit.getTypeDecls()) if (tree instanceof ClassTree c)
                scanner.fixtureOwners.add((unit.getPackageName() == null ? "" : unit.getPackageName() + ".") + c.getSimpleName());
            for (CompilationUnitTree unit : units) for (Tree tree : unit.getTypeDecls()) if (tree instanceof ClassTree c
                    && c.getSimpleName().contentEquals("PublicCaller"))
                for (Tree member : c.getMembers()) if (member instanceof MethodTree m && m.getName().contentEquals("observe")
                        && m.getParameters().size() == 1) {
                    Map<String, Object> env = new HashMap<>();
                    env.put(m.getParameters().get(0).getName().toString(), arguments);
                    scanner.scan(TreePath.getPath(unit, m.getBody()), env);
                }
            long errors = diagnostics.getDiagnostics().stream().filter(d -> d.getKind() == Diagnostic.Kind.ERROR).count();
            scanner.row("analysis", Long.toString(errors), "static declarations only");
            Files.write(root.resolve("facts"), scanner.rows, StandardCharsets.UTF_8);
        }
    }
}
