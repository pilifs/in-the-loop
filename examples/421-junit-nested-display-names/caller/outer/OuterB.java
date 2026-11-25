package outer;

import org.junit.jupiter.api.*;

@IndicativeSentencesGeneration(separator = " -> ", generator = DisplayNameGenerator.ReplaceUnderscores.class)
public class OuterB {
    @Nested
    class Ready_state {
        @Test
        void accepts_input() {}
    }
}
