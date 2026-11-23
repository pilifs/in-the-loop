import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "Lift#primitiveGood", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.primitiveGood(0, 1)), fields());
        row(1, fields("entry", "Lift#primitiveGood", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.primitiveGood(1, 0)), fields());
        row(2, fields("entry", "Lift#primitiveGood", "arguments", new String[]{"-1", "-1"}),
                fields("holds", Lift.primitiveGood(-1, -1)), fields());
        row(3, fields("entry", "Lift#primitiveGood", "arguments", new String[]{"Integer.MIN_VALUE", "Integer.MAX_VALUE"}),
                fields("holds", Lift.primitiveGood(Integer.MIN_VALUE, Integer.MAX_VALUE)), fields());
        row(4, fields("entry", "Lift#primitiveWrong", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.primitiveWrong(1, 0)), fields());
        row(5, fields("entry", "Lift#primitiveWrong", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.primitiveWrong(0, 1)), fields());
        row(6, fields("entry", "Lift#boxedGood", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.boxedGood(0, 1)), fields());
        row(7, fields("entry", "Lift#boxedGood", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.boxedGood(1, 0)), fields());
        row(8, fields("entry", "Lift#boxedGood", "arguments", new String[]{"-1", "-1"}),
                fields("holds", Lift.boxedGood(-1, -1)), fields());
        row(9, fields("entry", "Lift#boxedGood", "arguments", new String[]{"Integer.MIN_VALUE", "Integer.MAX_VALUE"}),
                fields("holds", Lift.boxedGood(Integer.MIN_VALUE, Integer.MAX_VALUE)), fields());
        row(10, fields("entry", "Lift#boxedWrong", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.boxedWrong(1, 0)), fields());
        row(11, fields("entry", "Lift#boxedWrong", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.boxedWrong(0, 1)), fields());
        row(12, fields("entry", "Lift#returnGood", "arguments", new String[]{"(short)0", "(short)1"}),
                fields("holds", Lift.returnGood((short)0, (short)1)), fields());
        row(13, fields("entry", "Lift#returnGood", "arguments", new String[]{"(short)3", "(short)-1"}),
                fields("holds", Lift.returnGood((short)3, (short)-1)), fields());
        row(14, fields("entry", "Lift#returnGood", "arguments", new String[]{"Short.MIN_VALUE", "Short.MAX_VALUE"}),
                fields("holds", Lift.returnGood(Short.MIN_VALUE, Short.MAX_VALUE)), fields());
        row(15, fields("entry", "Lift#returnWrong", "arguments", new String[]{"(short)3", "(short)-1"}),
                fields("holds", Lift.returnWrong((short)3, (short)-1)), fields());
        row(16, fields("entry", "Lift#returnWrong", "arguments", new String[]{"(short)0", "(short)1"}),
                fields("holds", Lift.returnWrong((short)0, (short)1)), fields());
        row(17, fields("entry", "Lift#boxedNull", "arguments", new String[]{}),
                fields("holds", Lift.boxedNull()), fields());
        row(18, fields("entry", "Lift#staticGood", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.staticGood(0, 1)), fields());
        row(19, fields("entry", "Lift#staticGood", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.staticGood(1, 0)), fields());
        row(20, fields("entry", "Lift#staticGood", "arguments", new String[]{"-1", "-1"}),
                fields("holds", Lift.staticGood(-1, -1)), fields());
        row(21, fields("entry", "Lift#staticGood", "arguments", new String[]{"Integer.MIN_VALUE", "Integer.MAX_VALUE"}),
                fields("holds", Lift.staticGood(Integer.MIN_VALUE, Integer.MAX_VALUE)), fields());
        row(22, fields("entry", "Lift#staticWrong", "arguments", new String[]{"1", "0"}),
                fields("holds", Lift.staticWrong(1, 0)), fields());
        row(23, fields("entry", "Lift#staticWrong", "arguments", new String[]{"0", "1"}),
                fields("holds", Lift.staticWrong(0, 1)), fields());
        row(24, fields("entry", "Chain#good", "arguments", new String[]{"0", "1"}),
                fields("holds", Chain.good(0, 1)), fields());
        row(25, fields("entry", "Chain#good", "arguments", new String[]{"1", "0"}),
                fields("holds", Chain.good(1, 0)), fields());
        row(26, fields("entry", "Chain#good", "arguments", new String[]{"-1", "-1"}),
                fields("holds", Chain.good(-1, -1)), fields());
        row(27, fields("entry", "Chain#good", "arguments", new String[]{"Integer.MIN_VALUE", "Integer.MAX_VALUE"}),
                fields("holds", Chain.good(Integer.MIN_VALUE, Integer.MAX_VALUE)), fields());
        row(28, fields("entry", "Chain#wrong", "arguments", new String[]{"1", "0"}),
                fields("holds", Chain.wrong(1, 0)), fields());
        row(29, fields("entry", "Chain#wrong", "arguments", new String[]{"0", "1"}),
                fields("holds", Chain.wrong(0, 1)), fields());
        row(30, fields("entry", "Chain#skipsNull", "arguments", new String[]{}),
                fields("holds", Chain.skipsNull()), fields());
        row(31, fields("entry", "Chain#rejectsNull", "arguments", new String[]{}),
                fields("holds", Chain.rejectsNull()), fields());
    }
}
