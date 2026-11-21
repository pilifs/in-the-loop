import ru.progrm_jarvis.reflector.bytecode.asm.AsmClassGenerator;
import ru.progrm_jarvis.reflector.bytecode.asm.EmptyConstructorCreator;
import ru.progrm_jarvis.reflector.bytecode.asm.SafeClassDefiner;

public final class UpgradeProbe {
    public static final class Example { public Example() { } }
    public static String observe(String[] args) {
        Class<?> target = args[0].equals("object") ? Object.class : Example.class;
        AsmClassGenerator generator = new AsmClassGenerator(new SafeClassDefiner());
        EmptyConstructorCreator<?> creator = generator.newClassInstanceManipulator(target);
        return creator.newInstance().getClass().getName();
    }
}
