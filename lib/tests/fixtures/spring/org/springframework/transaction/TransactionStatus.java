// A stand-in for the framework type of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the type and its members, which are the real ones.
package org.springframework.transaction;

public interface TransactionStatus {}
