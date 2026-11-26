# Bean overrides on a test that inherits its context hierarchy

Moving a two-level `@ContextHierarchy` declaration from the concrete Jupiter test to its abstract superclass caused both `@TestBean` variants on the subclass to fail during test preparation. The same five histories ran on the PR parent, landing and published Spring 7.1.0. This follow-up began with a failure during fixture construction and sits outside the campaign's 94 original predictions. [Caller](caller/PublicCaller.java) · [Registered follow-up](comparison.json)

| Where the concrete test gets its two levels | Field declared on the concrete test | PR parent | PR landing | 7.1.0 |
|---|---|---|---|---|
| Inherited | None | P / C | P / C | P / C |
| Direct | Unscoped override | X / X | X / X | X / X |
| Direct | Child-only override | X / X | P / X | P / X |
| Inherited | Unscoped override | Missing override registry | No override handler | No override handler |
| Inherited | Child-only override | Missing override registry | No override handler | No override handler |

P, C and X are greetings from the original parent service, original child service and replacement. Each successful test checked its two injected consumers against level-local lookups. The override field was identical to the child service. The parent revision ignores the new annotation member in the compiled direct child-only fixture. On the landing and 7.1.0 both inherited field overrides raised `IllegalStateException` before Jupiter invoked the test method. [Original revision observations](observations.json) · [Spring 7.1.0 observations](release-observations.json)

`@ContextHierarchy` is declared `@Inherited`. At the landing the bootstrapper builds each level for the class declaring its configuration. The override customizer searches the test class it receives for handlers, and the injection listener later looks for handlers for the fields on the concrete test. The observed failure is consistent with those two steps seeing different classes. [ContextHierarchy](https://github.com/spring-projects/spring-framework/blob/c168e1c2976267630d86c7114cf934a0f01aa8c9/spring-test/src/main/java/org/springframework/test/context/ContextHierarchy.java) · [Bootstrapper](https://github.com/spring-projects/spring-framework/blob/c168e1c2976267630d86c7114cf934a0f01aa8c9/spring-test/src/main/java/org/springframework/test/context/support/AbstractTestContextBootstrapper.java) · [Override customizer](https://github.com/spring-projects/spring-framework/blob/c168e1c2976267630d86c7114cf934a0f01aa8c9/spring-test/src/main/java/org/springframework/test/context/bean/override/BeanOverrideContextCustomizerFactory.java)

Run `python3 examples/501-spring-context-level-override/inherited-hierarchy/check_hierarchy.py` with the campaign caches. It recompiles the registered caller, runs all 15 histories, and checks the classpath, caller bytecode, and exact outcomes on all three deployments.
