package organic;

import org.apache.commons.lang3.StringUtils;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static int[] units(String text) {
        int[] out = new int[text.length()];
        for (int i = 0; i < out.length; i++) out[i] = text.charAt(i);
        return out;
    }

    public static void main(String[] args) {
        int code = 0;
        for (int node = 1; node <= 31; node++) {
            String text = SurrogateCuts.spelling(node);
            int side = text.length() + 2;
            for (int start = 0; start < side; start++) {
                for (int width = 0; width < side; width++, code++) {
                    int fixedStart = code % 36 / 6, fixedWidth = code % 6, abbreviatedWidth = 4 + code % 2;
                    row(code, fields("units", units(text), "start", start, "width", width),
                        fields("truncate", units(StringUtils.truncate(text, start, width)),
                               "fixedCut", units(StringUtils.truncate(SurrogateCuts.MIXED, fixedStart, fixedWidth)),
                               "abbreviate", units(StringUtils.abbreviate("\ud83d\ude00abcdef", abbreviatedWidth))),
                        fields("truncate", SurrogateCuts.truncate(code), "fixedCut", SurrogateCuts.fixedCut(code),
                               "abbreviate", SurrogateCuts.abbreviate(code)));
                }
            }
        }
    }
}
