import java.lang.reflect.*;
import java.util.*;

/** Bounded public action search. A separate auditor may inspect each completed transition. */
public final class ActionCensus {
    public record Arc(Object source, Object target, Object edge, int number) {}
    public interface Audit {
        void check(Object root, Object[] atoms, List<Arc> history, Arc attempt, String outcome);
    }
    static final class Factory {
        final Method generated;
        final Field root;
        final Object[] arguments;
        Factory(Method method, Field field, Object[] args) { generated=method; root=field; arguments=args; }
        Object make() throws ReflectiveOperationException {
            root.set(null,null);
            if(!Boolean.TRUE.equals(generated.invoke(null,arguments))) throw new IllegalStateException("producer did not yield an observed receiver");
            return Objects.requireNonNull(root.get(null));
        }
    }
    static String prefix(String name) {
        int i=0; while(i<name.length()&&Character.isLowerCase(name.charAt(i)))i++;
        return name.substring(0,i);
    }
    static String invoke(Method method,Object root,Object... args) throws ReflectiveOperationException {
        try { return Boolean.toString((boolean)method.invoke(root,args)); }
        catch(InvocationTargetException e) { return "throws:"+e.getCause().getClass().getName(); }
    }
    static int count(Factory maker,Method register,Method target,int atoms,int priorBound,Audit audit) throws ReflectiveOperationException {
        Object[] labels=new Object[atoms];
        for(int i=0;i<atoms;i++) labels[i]=new String("label"+i);
        List<int[]> pairs=new ArrayList<>();
        for(int i=0;i<atoms;i++)for(int j=0;j<atoms;j++)if(i!=j)pairs.add(new int[]{i,j});
        if(pairs.size()>16)throw new IllegalArgumentException("finite pair limit");
        int transitions=0;
        for(int mask=0;mask<1<<pairs.size();mask++) {
            if(Integer.bitCount(mask)>priorBound)continue;
            for(int ordinal=0;ordinal<pairs.size();ordinal++){
                Object root=maker.make();
                for(Object v:labels) {
                    String r=invoke(register,root,v);
                    if(!r.equals("true")){System.out.println("setup-miss\t"+register+"\t"+r);return transitions;}
                }
                List<Arc> history=new ArrayList<>();boolean attainable=true;
                for(int i=0;i<pairs.size();i++)if((mask & (1<<i))!=0) {
                    int[] arc=pairs.get(i); Object edge=new Object();
                    String r=invoke(target,root,labels[arc[0]],labels[arc[1]],edge);
                    if(!r.equals("true")){attainable=false;break;}
                    history.add(new Arc(labels[arc[0]],labels[arc[1]],edge,i));
                }
                if(!attainable)break;
                int[] pair=pairs.get(ordinal);
                Arc attempt=new Arc(labels[pair[0]],labels[pair[1]],new Object(),ordinal);
                String outcome=invoke(target,root,attempt.source,attempt.target,attempt.edge);
                if(audit!=null)audit.check(root,labels,history,attempt,outcome);
                System.out.println("transition\t"+mask+"\t"+ordinal+"\t"+outcome);transitions++;
            }
        }
        return transitions;
    }
    public static void main(String[] args) throws Exception {
        // receiver class, public action, generated entry, capture field, atom bound, prior-action bound, optional audit
        Class<?> receiver=Class.forName(args[0]);
        String[] entry=args[2].split("#"),field=args[3].split("#");
        Method maker=Arrays.stream(Class.forName(entry[0]).getMethods()).filter(m->m.getName().equals(entry[1])).findFirst().orElseThrow();
        Field capture=Class.forName(field[0]).getField(field[1]);
        Method target=receiver.getMethod(args[1],Object.class,Object.class,Object.class);
        if(target.getReturnType()!=boolean.class || Modifier.isStatic(target.getModifiers()))throw new IllegalArgumentException("action signature");
        List<Method> registration=Arrays.stream(receiver.getMethods()).filter(m->
            !m.isBridge() && !m.isSynthetic() && !Modifier.isStatic(m.getModifiers()) && m.getReturnType()==boolean.class &&
            m.getParameterCount()==1 && m.getParameterTypes()[0].isAssignableFrom(String.class) &&
            prefix(m.getName()).equals(prefix(target.getName()))).sorted(Comparator.comparing(Method::toString)).toList();
        Audit audit=args.length==7?(Audit)Class.forName(args[6]).getConstructor().newInstance():null;
        if(registration.isEmpty())System.out.println("producer-miss\tno compatible public registration action");
        for(Class<?> t:maker.getParameterTypes())if(t!=boolean.class){System.out.println("producer-miss\tno finite seed domain for "+t);return;}
        if(maker.getParameterCount()>6)throw new IllegalArgumentException("Boolean seed cap");
        for(int flags=0;flags<1<<maker.getParameterCount();flags++) {
            Object[] inputs=new Object[maker.getParameterCount()];for(int i=0;i<inputs.length;i++)inputs[i]=(flags&(1<<i))!=0;
            Factory factory=new Factory(maker,capture,inputs);
            for(Method reg:registration) {
                System.out.println("candidate\t"+entry[1]+"\t"+flags+"\t"+reg.getName());
                try { int n=count(factory,reg,target,Integer.parseInt(args[4]),Integer.parseInt(args[5]),audit);System.out.println("total\t"+n); }
                catch(InvocationTargetException failed){System.out.println("producer-miss\t"+failed.getCause().getClass().getName());}
            }
        }
    }
}
