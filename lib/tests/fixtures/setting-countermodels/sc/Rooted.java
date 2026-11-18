package sc;

import java.io.File;

/** The working directory, as a relative file's absolute path gives it: user.dir, which the JDK read at startup. */
public class Rooted {
    public static final String DIR = new File("").getAbsolutePath();
}
