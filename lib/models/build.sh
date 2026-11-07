#!/bin/sh
# Compiles the models in java/ into classes/, which the crate embeds (src/models.rs) and a test compares against the
# sources. Run it after changing a model, from any directory; it needs a javac that still accepts --release 8, the
# class file version JBMC 6 reads best (the models use nothing newer).
set -eu
cd "$(dirname "$0")"
rm -rf classes
mkdir -p classes
# The models of java.lang classes are compiled in a run of their own: given a source for java.lang.Character, javac
# compiles the other models against the model rather than the JDK's class.
javac --release 8 -Xlint:-options -g -d classes java/lang/*.java
javac --release 8 -Xlint:-options -g -d classes java/nio/charset/*.java
javac --release 8 -Xlint:-options -g -d classes java/util/*.java
find classes -name '*.class' | sort
