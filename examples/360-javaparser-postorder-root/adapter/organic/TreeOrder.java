package organic;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.PackageDeclaration;
import java.util.EmptyStackException;
import java.util.Iterator;
import java.util.List;

public final class TreeOrder {
    static CompilationUnit tree(int code) { return code == 0 ? new CompilationUnit() : new CompilationUnit("com"); }

    static Node[] expected(CompilationUnit root, boolean post) {
        if (!root.getPackageDeclaration().isPresent()) return new Node[]{root};
        PackageDeclaration pkg = root.getPackageDeclaration().get();
        return post ? new Node[]{pkg.getName(), pkg, root} : new Node[]{root, pkg, pkg.getName()};
    }

    static int find(int code, boolean post) {
        CompilationUnit root = tree(code);
        Node[] want = expected(root, post);
        try {
            Node receiver = root;
            List<Node> got = receiver.findAll(Node.class, post ? Node.TreeTraversal.POSTORDER : Node.TreeTraversal.PREORDER);
            if (got.size() != want.length) return 0;
            for (int i = 0; i < want.length; i++) if (got.get(i) != want[i]) return 0;
            return 1;
        } catch (EmptyStackException exhaustedEarly) {
            return 0;
        }
    }

    public static int postorder(int code) { return find(code, true); }
    public static int preorder(int code) { return find(code, false); }

    public static int terminal(int code) {
        CompilationUnit root = tree(code);
        Node[] want = expected(root, true);
        try {
            Iterator<Node> it = new Node.PostOrderIterator(root);
            for (Node node : want) if (!it.hasNext() || it.next() != node) return 0;
            return !it.hasNext() && !it.hasNext() ? 1 : 0;
        } catch (EmptyStackException exhaustedEarly) {
            return 0;
        }
    }
}
