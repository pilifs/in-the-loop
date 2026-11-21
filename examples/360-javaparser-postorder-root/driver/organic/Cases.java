package organic;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Node;
import java.util.ArrayList;
import java.util.EmptyStackException;
import java.util.Iterator;
import java.util.List;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static String name(CompilationUnit root, Node node) {
        if (node == root) return "root";
        if (root.getPackageDeclaration().isPresent()) {
            if (node == root.getPackageDeclaration().get()) return "package";
            if (node == root.getPackageDeclaration().get().getName()) return "name";
        }
        return "different-object";
    }

    static Object find(CompilationUnit root, Node.TreeTraversal order) {
        try {
            List<String> ids = new ArrayList<>();
            for (Node node : root.findAll(Node.class, order)) ids.add(name(root, node));
            return ids;
        } catch (EmptyStackException e) { return e.getClass().getName(); }
    }

    static Object traversal(CompilationUnit root) {
        List<String> ids = new ArrayList<>();
        try {
            Iterator<Node> it = new Node.PostOrderIterator(root);
            while (it.hasNext() && ids.size() < 5) ids.add(name(root, it.next()));
            return fields("nodes", ids, "exhausted", !it.hasNext() && !it.hasNext());
        } catch (EmptyStackException e) { return e.getClass().getName(); }
    }

    public static void main(String[] args) {
        for (int code = 0; code < 2; code++) {
            CompilationUnit root = TreeOrder.tree(code);
            row(code, fields("package", code == 0 ? "" : "com"),
                fields("postorder", find(root, Node.TreeTraversal.POSTORDER), "preorder", find(root, Node.TreeTraversal.PREORDER),
                       "terminal", traversal(root)),
                fields("postorder", TreeOrder.postorder(code), "preorder", TreeOrder.preorder(code), "terminal", TreeOrder.terminal(code)));
        }
    }
}
