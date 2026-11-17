package org.xml.sax.helpers;

/**
 * A class path copy of a class of the JDK's module java.xml, as a JAR like xml-apis carries one: a JVM loads the
 * module's class (getLength() of an empty AttributesImpl is 0) and never this one. Compiled with --release 8, which
 * has no modules.
 */
public class AttributesImpl {
    public int getLength() {
        return 42;
    }
}
