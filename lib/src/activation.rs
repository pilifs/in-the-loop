//! Activation: which configuration switches each annotation family of a module on. An `@Scheduled` method runs
//! only when a configuration carries `@EnableScheduling`; `@Async`, `@Cacheable`, `@PreAuthorize`, `@Secured`,
//! `@Retryable` and an `@Aspect` each have their own switch; `@Transactional`, `@KafkaListener` and method
//! validation are switched on by Spring Boot's auto-configuration when its conditions hold; `@Valid` needs a
//! Bean Validation provider on the class path; `@Timed` needs the aspect bean the AspectJ weaver makes possible.
//! Without the switch nobody reads the annotation: the code compiles, the context starts, every test that does not
//! depend on the advice passes, and the method is never scheduled, never cached, never secured.
//!
//! The block names, for each family the module uses, what enables it: the configuration class with the `@Enable`
//! annotation and how it is reached (local, imported, scanned from a dependency, auto-configured), the bean that
//! applies the advice, or the provider on the class path. A family nothing enables is a `!` line, with the nearest
//! miss when there is one: a configuration that carries the switch but is not a component, is outside the scanned
//! packages, or is an auto-configuration whose condition fails.
//!
//! What counts as a configuration in scope: the local classes with a stereotype in the scanned packages (the
//! application class's package and its `scanBasePackages`, or every local class when the module has no
//! application class), the classes of the class path in those packages, the `@Import`s of each, their nested
//! configuration classes, the auto-configurations listed in
//! `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` and `spring.factories` on
//! the class path minus the application's `exclude`s, and their imports and nested classes in turn.
//! `@ConditionalOnClass`, `@ConditionalOnMissingClass`, `@ConditionalOnResource`, `@ConditionalOnWebApplication`
//! and `@ConditionalOnNotWebApplication` are evaluated against the class path; the other conditions
//! (`@ConditionalOnBean`, `@ConditionalOnProperty`, `@Profile`) are taken as met. Meta-annotations are followed
//! three levels deep, so `@EnableAsync` on an annotation of the application's own counts, and `@Service` is a
//! `@Component`.

use std::collections::{BTreeMap, BTreeSet};
use std::rc::Rc;

use crate::boundaries::{Bean, Member};
use crate::classfile::{flags, simple_name_of, Annotation, ClassFile, ElementValue, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::Error;

const IMPORTS: &str = "META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports";
const FACTORIES: &str = "META-INF/spring.factories";
const FACTORIES_KEY: &str = "org.springframework.boot.autoconfigure.EnableAutoConfiguration";
const PROVIDERS: &[&str] = &["META-INF/services/jakarta.validation.spi.ValidationProvider", "META-INF/services/javax.validation.spi.ValidationProvider"];

const COMPONENT: &str = "org/springframework/stereotype/Component";
/// Stereotypes known by name, for a class path without the framework's annotation classes to follow.
const STEREOTYPES: &[&str] = &["Component", "Service", "Repository", "Controller", "RestController", "Configuration", "SpringBootApplication", "SpringBootConfiguration", "ControllerAdvice", "RestControllerAdvice", "TestConfiguration"];
const SPRING_BOOT_APPLICATION: &str = "org/springframework/boot/autoconfigure/SpringBootApplication";
const ENABLE_AUTO_CONFIGURATION: &str = "org/springframework/boot/autoconfigure/EnableAutoConfiguration";
const COMPONENT_SCAN: &str = "org/springframework/context/annotation/ComponentScan";
const IMPORT: &str = "org/springframework/context/annotation/Import";
const BEAN: &str = "org/springframework/context/annotation/Bean";
const CONDITIONS: &str = "org/springframework/boot/autoconfigure/condition/";
const SERVLET_CONTEXT: &str = "org/springframework/web/context/support/GenericWebApplicationContext";
const REACTIVE_CONTEXT: &str = "org/springframework/web/reactive/HandlerResult";

const ENABLE_METHOD_SECURITY: &str = "org/springframework/security/config/annotation/method/configuration/EnableMethodSecurity";
const ENABLE_GLOBAL_METHOD_SECURITY: &str = "org/springframework/security/config/annotation/method/configuration/EnableGlobalMethodSecurity";
const ENABLE_REACTIVE_METHOD_SECURITY: &str = "org/springframework/security/config/annotation/method/configuration/EnableReactiveMethodSecurity";

/// What switches a family on. Every need of a family must be met.
#[derive(Debug, Clone, Copy)]
enum Need {
    /// Any of these annotations on a configuration in scope, each with the boolean element that must be true and
    /// that element's default (`@EnableMethodSecurity(securedEnabled = true)`), or with no element to check.
    Enable(&'static [(&'static str, Option<(&'static str, bool)>)]),
    /// A `@Bean` method returning this type on a configuration in scope.
    Bean(&'static str),
    /// A Bean Validation provider on the class path.
    Provider,
}

struct Family {
    /// The family as the contract names it: `@Scheduled`.
    label: &'static str,
    /// The annotations (internal names) whose presence in the module means the family is used.
    uses: &'static [&'static str],
    needs: &'static [Need],
    /// What happens to the annotated code when nothing enables the family.
    without: &'static str,
}

const FAMILIES: &[Family] = &[
    Family {
        label: "@Scheduled",
        uses: &["org/springframework/scheduling/annotation/Scheduled", "org/springframework/scheduling/annotation/Schedules"],
        needs: &[Need::Enable(&[("org/springframework/scheduling/annotation/EnableScheduling", None)])],
        without: "a @Scheduled method never runs",
    },
    Family {
        label: "@Async",
        uses: &["org/springframework/scheduling/annotation/Async"],
        needs: &[Need::Enable(&[("org/springframework/scheduling/annotation/EnableAsync", None)])],
        without: "an @Async method runs on the caller's thread, which waits for it",
    },
    Family {
        label: "@Cacheable",
        uses: &["org/springframework/cache/annotation/Cacheable", "org/springframework/cache/annotation/CachePut", "org/springframework/cache/annotation/CacheEvict", "org/springframework/cache/annotation/Caching"],
        needs: &[Need::Enable(&[("org/springframework/cache/annotation/EnableCaching", None)])],
        without: "every call runs the method and nothing is cached or evicted",
    },
    Family {
        label: "@PreAuthorize",
        uses: &["org/springframework/security/access/prepost/PreAuthorize", "org/springframework/security/access/prepost/PostAuthorize", "org/springframework/security/access/prepost/PreFilter", "org/springframework/security/access/prepost/PostFilter"],
        needs: &[Need::Enable(&[(ENABLE_METHOD_SECURITY, Some(("prePostEnabled", true))), (ENABLE_GLOBAL_METHOD_SECURITY, Some(("prePostEnabled", false))), (ENABLE_REACTIVE_METHOD_SECURITY, None)])],
        without: "every caller is authorized",
    },
    Family {
        label: "@Secured",
        uses: &["org/springframework/security/access/annotation/Secured"],
        needs: &[Need::Enable(&[(ENABLE_METHOD_SECURITY, Some(("securedEnabled", false))), (ENABLE_GLOBAL_METHOD_SECURITY, Some(("securedEnabled", false)))])],
        without: "every caller is authorized",
    },
    Family {
        label: "@RolesAllowed",
        uses: &["jakarta/annotation/security/RolesAllowed", "jakarta/annotation/security/PermitAll", "jakarta/annotation/security/DenyAll", "javax/annotation/security/RolesAllowed", "javax/annotation/security/PermitAll", "javax/annotation/security/DenyAll"],
        needs: &[Need::Enable(&[(ENABLE_METHOD_SECURITY, Some(("jsr250Enabled", false))), (ENABLE_GLOBAL_METHOD_SECURITY, Some(("jsr250Enabled", false)))])],
        without: "every caller is authorized",
    },
    Family {
        label: "@Transactional",
        uses: &["org/springframework/transaction/annotation/Transactional", "jakarta/transaction/Transactional", "javax/transaction/Transactional"],
        needs: &[Need::Enable(&[("org/springframework/transaction/annotation/EnableTransactionManagement", None)])],
        without: "every call runs without a transaction and nothing rolls back",
    },
    Family {
        label: "@Retryable",
        uses: &["org/springframework/retry/annotation/Retryable", "org/springframework/retry/annotation/CircuitBreaker"],
        needs: &[Need::Enable(&[("org/springframework/retry/annotation/EnableRetry", None)])],
        without: "a failing call is not retried",
    },
    Family {
        label: "@Retryable (org.springframework.resilience)",
        uses: &["org/springframework/resilience/annotation/Retryable", "org/springframework/resilience/annotation/ConcurrencyLimit"],
        needs: &[Need::Enable(&[("org/springframework/resilience/annotation/EnableResilientMethods", None)])],
        without: "a failing call is not retried and no concurrency limit holds",
    },
    Family {
        label: "@Aspect",
        uses: &["org/aspectj/lang/annotation/Aspect"],
        needs: &[Need::Enable(&[("org/springframework/context/annotation/EnableAspectJAutoProxy", None)])],
        without: "the aspect's advice never runs",
    },
    Family {
        label: "@KafkaListener",
        uses: &["org/springframework/kafka/annotation/KafkaListener", "org/springframework/kafka/annotation/KafkaHandler"],
        needs: &[Need::Enable(&[("org/springframework/kafka/annotation/EnableKafka", None)])],
        without: "the listener never receives a message",
    },
    Family {
        label: "@RabbitListener",
        uses: &["org/springframework/amqp/rabbit/annotation/RabbitListener", "org/springframework/amqp/rabbit/annotation/RabbitHandler"],
        needs: &[Need::Enable(&[("org/springframework/amqp/rabbit/annotation/EnableRabbit", None)])],
        without: "the listener never receives a message",
    },
    Family {
        label: "@JmsListener",
        uses: &["org/springframework/jms/annotation/JmsListener"],
        needs: &[Need::Enable(&[("org/springframework/jms/annotation/EnableJms", None)])],
        without: "the listener never receives a message",
    },
    Family {
        label: "@WebFilter",
        uses: &["jakarta/servlet/annotation/WebFilter", "jakarta/servlet/annotation/WebServlet", "jakarta/servlet/annotation/WebListener"],
        needs: &[Need::Enable(&[("org/springframework/boot/web/servlet/ServletComponentScan", None), ("org/springframework/boot/servlet/ServletComponentScan", None)])],
        without: "the servlet component is not registered with the embedded container",
    },
    Family {
        label: "@Valid",
        uses: &["jakarta/validation/Valid", "javax/validation/Valid"],
        needs: &[Need::Provider],
        without: "nothing is validated and an invalid body is accepted",
    },
    Family {
        label: "@Validated",
        uses: &["org/springframework/validation/annotation/Validated"],
        needs: &[Need::Provider, Need::Bean("org/springframework/validation/beanvalidation/MethodValidationPostProcessor")],
        without: "the constraints on the bean's methods are never checked",
    },
    Family {
        label: "@Timed",
        uses: &["io/micrometer/core/annotation/Timed"],
        needs: &[Need::Bean("io/micrometer/core/aop/TimedAspect")],
        without: "no timer is recorded",
    },
    Family {
        label: "@Counted",
        uses: &["io/micrometer/core/annotation/Counted"],
        needs: &[Need::Bean("io/micrometer/core/aop/CountedAspect")],
        without: "no counter is recorded",
    },
    Family {
        label: "@Observed",
        uses: &["io/micrometer/observation/annotation/Observed"],
        needs: &[Need::Bean("io/micrometer/observation/aop/ObservedAspect")],
        without: "no observation is recorded",
    },
];

/// How a configuration in scope is reached.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum How {
    Local,
    /// By `@Import`, from this local class (internal name).
    Imported(String),
    /// By component scanning, from a class path entry other than the module's own.
    Scanned,
    AutoConfigured,
}

#[derive(Debug, Clone)]
struct Place {
    /// Internal name.
    class: String,
    how: How,
    /// The condition that keeps this configuration out of the context, if one fails.
    inactive: Option<String>,
}

impl Place {
    fn rank(&self) -> (u8, &str) {
        let rank = match self.how {
            How::Local => 0,
            How::Imported(_) => 1,
            How::Scanned => 2,
            How::AutoConfigured => 3,
        };
        (rank, &self.class)
    }

    /// `net.terminalvalue.boxoffice.messaging.MessagingConfiguration, imported by TicketingApplication`, or for an
    /// auto-configuration its class and nesting alone: `KafkaAnnotationDrivenConfiguration.EnableKafkaConfiguration`.
    fn render(&self) -> String {
        let name = match self.how {
            How::AutoConfigured => simple_name_of(self.class.split('$').next().unwrap_or(&self.class)) + &self.class[self.class.split('$').next().map_or(0, str::len)..],
            _ => self.class.clone(),
        };
        let name = name.replace(['/', '$'], ".");
        match &self.how {
            How::Local => name,
            How::Imported(by) => format!("{name}, imported by {}", simple_name_of(by)),
            How::Scanned => format!("{name}, scanned"),
            How::AutoConfigured => format!("{name}, auto-configured"),
        }
    }
}

struct Walk<'a> {
    cp: &'a ClassPath,
    classes: &'a BTreeMap<String, Rc<ClassFile>>,
    visited: BTreeSet<String>,
    /// The switches worth recording (every annotation a family needs), by internal name, with where each is found.
    wanted: BTreeSet<&'static str>,
    enables: BTreeMap<String, Vec<(Annotation, Place)>>,
    /// `@Bean` return types (internal names) with where each is defined.
    beans: BTreeMap<String, Vec<Place>>,
}

impl Walk<'_> {
    fn class(&self, name: &str) -> Option<Rc<ClassFile>> {
        if let Some(c) = self.classes.get(name) {
            return Some(c.clone());
        }
        self.cp.load(name).ok().flatten().map(|l| l.class)
    }

    /// The annotations on the class and their meta-annotations, three levels deep, each type once.
    fn expand(&self, direct: &[Annotation]) -> Vec<Annotation> {
        let mut out: Vec<Annotation> = Vec::new();
        let mut seen: BTreeSet<String> = BTreeSet::new();
        let mut frontier: Vec<Annotation> = direct.to_vec();
        for _depth in 0..3 {
            let mut next = Vec::new();
            for a in frontier {
                if !seen.insert(a.type_name.clone()) {
                    continue;
                }
                if !a.type_name.starts_with("java/") {
                    if let Some(class) = self.class(&a.type_name) {
                        if let Ok(meta) = class.annotations() {
                            next.extend(meta);
                        }
                    }
                }
                out.push(a);
            }
            if next.is_empty() {
                break;
            }
            frontier = next;
        }
        out
    }

    /// The first Boot condition among the annotations that fails against the class path, as a reason.
    fn failing(&self, annotations: &[Annotation]) -> Option<String> {
        for a in annotations {
            let Some(kind) = a.type_name.strip_prefix(CONDITIONS) else { continue };
            match kind {
                "ConditionalOnClass" => {
                    let mut names = a.classes("value");
                    names.extend(a.strings("name").into_iter().map(|n| n.replace('.', "/")));
                    if let Some(missing) = names.iter().find(|n| !self.cp.exists(n)) {
                        return Some(format!("{} is not on the class path", missing.replace(['/', '$'], ".")));
                    }
                }
                "ConditionalOnMissingClass" => {
                    if let Some(present) = a.strings("value").into_iter().find(|n| self.cp.exists(&n.replace('.', "/"))) {
                        return Some(format!("{present} is on the class path"));
                    }
                }
                "ConditionalOnResource" => {
                    for r in a.strings("resources") {
                        let path = r.strip_prefix("classpath:").unwrap_or(&r).trim_start_matches('/');
                        if self.cp.resources(path).map_or(true, |found| found.is_empty()) {
                            return Some(format!("no {path} on the class path"));
                        }
                    }
                }
                "ConditionalOnWebApplication" => {
                    let wanted = a.enum_names("type").into_iter().next().unwrap_or_else(|| "ANY".to_string());
                    let servlet = self.cp.exists(SERVLET_CONTEXT);
                    let reactive = self.cp.exists(REACTIVE_CONTEXT);
                    let met = match wanted.as_str() {
                        "SERVLET" => servlet,
                        "REACTIVE" => reactive,
                        _ => servlet || reactive,
                    };
                    if !met {
                        return Some(format!("not a {} web application", wanted.to_lowercase()));
                    }
                }
                "ConditionalOnNotWebApplication" if self.cp.exists(SERVLET_CONTEXT) || self.cp.exists(REACTIVE_CONTEXT) => {
                    return Some("a web application".to_string());
                }
                _ => {}
            }
        }
        None
    }

    fn visit(&mut self, name: &str, how: How, inactive: Option<String>) {
        if !self.visited.insert(name.to_string()) {
            return;
        }
        let Some(class) = self.class(name) else { return };
        if class.access & flags::ANNOTATION != 0 {
            return;
        }
        let direct = class.annotations().unwrap_or_default();
        let inactive = inactive.or_else(|| self.failing(&direct));
        let expanded = self.expand(&direct);
        let place = Place { class: name.to_string(), how: how.clone(), inactive: inactive.clone() };
        for a in &expanded {
            if self.wanted.contains(a.type_name.as_str()) {
                self.enables.entry(a.type_name.clone()).or_default().push((a.clone(), place.clone()));
            }
        }
        for method in &class.methods {
            let annotations = method.annotations(&class.pool).unwrap_or_default();
            if !annotations.iter().any(|a| a.type_name == BEAN) {
                continue;
            }
            let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
            let Type::Object(ret) = d.ret else { continue };
            let inactive = inactive.clone().or_else(|| self.failing(&annotations));
            self.beans.entry(ret).or_default().push(Place { class: name.to_string(), how: how.clone(), inactive });
        }
        // What an imported class imports is reached the same way; an auto-configuration's imports stay
        // auto-configured.
        let onward = match &how {
            How::Local => How::Imported(name.to_string()),
            other => other.clone(),
        };
        for a in &expanded {
            if a.type_name == IMPORT {
                for imported in a.classes("value") {
                    self.visit(&imported, onward.clone(), inactive.clone());
                }
            }
        }
        if let Ok(inner) = class.inner_classes() {
            let nested: Vec<String> = inner.iter().filter(|i| i.outer.as_deref() == Some(name) && i.inner != name && i.access & flags::STATIC != 0).map(|i| i.inner.clone()).collect();
            for n in nested {
                self.visit(&n, how.clone(), inactive.clone());
            }
        }
    }
}

fn package_of(internal: &str) -> &str {
    internal.rsplit_once('/').map_or("", |(p, _)| p)
}

fn is_component(expanded: &[Annotation]) -> bool {
    expanded.iter().any(|a| a.type_name == COMPONENT || (a.type_name.starts_with("org/springframework/") && STEREOTYPES.contains(&a.simple_name().as_str())))
}

/// The packages (internal form, without a trailing slash) a class's `@SpringBootApplication` or `@ComponentScan`
/// scans, defaulting to its own.
fn scan_packages(name: &str, direct: &[Annotation]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    for a in direct {
        let (packages, classes) = match a.type_name.as_str() {
            SPRING_BOOT_APPLICATION => (["scanBasePackages"].as_slice(), "scanBasePackageClasses"),
            COMPONENT_SCAN => (["value", "basePackages"].as_slice(), "basePackageClasses"),
            _ => continue,
        };
        for element in packages {
            out.extend(a.strings(element).into_iter().map(|p| p.replace('.', "/")));
        }
        out.extend(a.classes(classes).iter().map(|c| package_of(c).to_string()));
    }
    if out.is_empty() {
        out.insert(package_of(name).to_string());
    }
    out
}

fn excluded_auto_configurations(direct: &[Annotation]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    for a in direct {
        if a.type_name == SPRING_BOOT_APPLICATION || a.type_name == ENABLE_AUTO_CONFIGURATION {
            out.extend(a.classes("exclude").into_iter().map(|c| c.replace('/', ".")));
            out.extend(a.strings("excludeName"));
        }
    }
    out
}

/// The auto-configuration class names (dotted) the class path registers, in class path order, each once.
fn auto_configurations(cp: &ClassPath) -> Result<Vec<String>, Error> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let mut add = |name: &str| {
        let name = name.trim();
        if !name.is_empty() && seen.insert(name.to_string()) {
            out.push(name.to_string());
        }
    };
    for (_, bytes) in cp.resources(IMPORTS)? {
        for line in String::from_utf8_lossy(&bytes).lines() {
            let line = line.split('#').next().unwrap_or("");
            add(line);
        }
    }
    for (_, bytes) in cp.resources(FACTORIES)? {
        for name in factories_value(&String::from_utf8_lossy(&bytes), FACTORIES_KEY) {
            add(&name);
        }
    }
    Ok(out)
}

/// The comma-separated values of a key in a properties file with `\` continuation lines.
fn factories_value(text: &str, key: &str) -> Vec<String> {
    let mut joined = String::new();
    let mut continued = false;
    for raw in text.lines() {
        let line = raw.trim();
        if continued {
            joined.push_str(line.trim_end_matches('\\'));
            continued = line.ends_with('\\');
            if !continued {
                joined.push('\n');
            }
            continue;
        }
        joined.push_str(line.trim_end_matches('\\'));
        continued = line.ends_with('\\');
        if !continued {
            joined.push('\n');
        }
    }
    joined
        .lines()
        .filter_map(|l| l.split_once('='))
        .filter(|(k, _)| k.trim() == key)
        .flat_map(|(_, v)| v.split(',').map(|s| s.trim().to_string()).collect::<Vec<_>>())
        .filter(|s| !s.is_empty())
        .collect()
}

/// Whether the annotation found is the switch the need asks for, with its element set.
fn satisfies(annotation: &Annotation, element: Option<(&str, bool)>) -> bool {
    match element {
        None => true,
        Some((name, default)) => match annotation.element(name) {
            Some(ElementValue::Boolean(b)) => *b,
            _ => default,
        },
    }
}

/// `@EnableMethodSecurity(securedEnabled = true)`: the switch as the need names it.
fn render_switch(name: &str, element: Option<(&str, bool)>) -> String {
    match element {
        Some((e, false)) => format!("@{}({e} = true)", simple_name_of(name)),
        _ => format!("@{}", simple_name_of(name)),
    }
}

/// The activation block of a module: `None` when its local classes use none of the families.
pub fn analyse(cp: &ClassPath, classes: &BTreeMap<String, Rc<ClassFile>>, only: Option<&BTreeSet<String>>) -> Result<Option<Bean>, Error> {
    let mut wanted: BTreeSet<&'static str> = BTreeSet::new();
    let mut uses: BTreeSet<&'static str> = BTreeSet::new();
    for f in FAMILIES {
        uses.extend(f.uses);
        for n in f.needs {
            if let Need::Enable(list) = n {
                wanted.extend(list.iter().map(|(name, _)| *name));
            }
        }
    }
    let mut walk = Walk { cp, classes, visited: BTreeSet::new(), wanted, enables: BTreeMap::new(), beans: BTreeMap::new() };

    // Which families the module uses, and the first class using each.
    let local: Vec<(&String, &Rc<ClassFile>)> = classes.iter().filter(|(name, class)| only.is_none_or(|set| set.contains(*name)) && class.access & (flags::ANNOTATION | flags::SYNTHETIC) == 0).collect();
    let mut users: BTreeMap<&'static str, String> = BTreeMap::new();
    for (name, class) in &local {
        let mut found: Vec<String> = Vec::new();
        found.extend(class.annotations().unwrap_or_default().into_iter().map(|a| a.type_name));
        for f in &class.fields {
            found.extend(f.annotations(&class.pool).unwrap_or_default().into_iter().map(|a| a.type_name));
        }
        for m in &class.methods {
            found.extend(m.annotations(&class.pool).unwrap_or_default().into_iter().map(|a| a.type_name));
            found.extend(m.parameter_annotations(&class.pool).unwrap_or_default().into_iter().flatten().map(|a| a.type_name));
        }
        for t in found {
            if let Some(family) = FAMILIES.iter().find(|f| f.uses.contains(&t.as_str())) {
                users.entry(family.label).or_insert_with(|| (*name).clone());
            }
        }
    }
    if users.is_empty() {
        return Ok(None);
    }

    // The application classes, the packages they scan and the auto-configurations they exclude.
    let mut applications: Vec<String> = Vec::new();
    let mut scan: BTreeSet<String> = BTreeSet::new();
    let mut excluded: BTreeSet<String> = BTreeSet::new();
    let mut boot = false;
    let mut expanded_local: BTreeMap<&str, (Vec<Annotation>, Vec<Annotation>)> = BTreeMap::new();
    for (name, class) in &local {
        let direct = class.annotations().unwrap_or_default();
        let expanded = walk.expand(&direct);
        let application = expanded.iter().any(|a| a.type_name == ENABLE_AUTO_CONFIGURATION || a.type_name == COMPONENT_SCAN);
        if application {
            boot |= expanded.iter().any(|a| a.type_name == ENABLE_AUTO_CONFIGURATION);
            applications.push((*name).clone());
            scan.extend(scan_packages(name, &direct));
            // `@SpringBootApplication`'s own elements are on the direct annotation; its meta `@ComponentScan` has none.
            for a in &expanded {
                if a.type_name == SPRING_BOOT_APPLICATION || a.type_name == COMPONENT_SCAN {
                    scan.extend(scan_packages(name, std::slice::from_ref(a)));
                }
            }
            excluded.extend(excluded_auto_configurations(&direct));
            for a in &expanded {
                excluded.extend(excluded_auto_configurations(std::slice::from_ref(a)));
            }
        }
        expanded_local.insert(name.as_str(), (direct, expanded));
    }
    let scanned = |name: &str| applications.is_empty() || scan.iter().any(|p| name.starts_with(&format!("{p}/")));
    boot |= applications.is_empty();

    // The configurations in scope, and why a local class is not one.
    let mut out_of_scope: BTreeMap<String, String> = BTreeMap::new();
    for (name, (_, expanded)) in &expanded_local {
        if !is_component(expanded) {
            out_of_scope.insert((*name).to_string(), "is not a component".to_string());
        } else if !scanned(name) {
            out_of_scope.insert((*name).to_string(), format!("is outside the scanned packages ({})", scan.iter().map(|p| p.replace('/', ".")).collect::<Vec<_>>().join(", ")));
        } else {
            walk.visit(name, How::Local, None);
        }
    }
    if !applications.is_empty() {
        let foreign: Vec<String> = classes.keys().filter(|n| only.is_some_and(|set| !set.contains(*n)) && scanned(n)).cloned().collect();
        for name in foreign {
            let class = &classes[&name];
            if class.access & (flags::ANNOTATION | flags::SYNTHETIC) != 0 {
                continue;
            }
            let direct = class.annotations().unwrap_or_default();
            if !direct.is_empty() && is_component(&walk.expand(&direct)) {
                walk.visit(&name, How::Scanned, None);
            }
        }
    }
    if boot {
        for name in auto_configurations(cp)? {
            if excluded.contains(&name) {
                continue;
            }
            walk.visit(&name.replace('.', "/"), How::AutoConfigured, None);
        }
    }

    // Each used family: what enables it, or why nothing does.
    let mut members = Vec::new();
    for family in FAMILIES {
        let Some(user) = users.get(family.label) else { continue };
        let mut parts: Vec<String> = Vec::new();
        let mut problem: Option<String> = None;
        for need in family.needs {
            match resolve(&walk, &expanded_local, &out_of_scope, *need)? {
                Ok(text) => parts.push(text),
                Err(reason) => {
                    problem = Some(reason);
                    break;
                }
            }
        }
        let (line, details, problems) = match problem {
            None => (format!("{}: {}", family.label, parts.join("; ")), Vec::new(), 0),
            Some(reason) => (format!("{}: nothing enables it", family.label), vec![format!("! {reason}: {}", family.without)], 1),
        };
        members.push(Member { line, details, entry: false, advised: false, problems, source_line: None, source_file: None, source_class: Some(user.clone()) });
    }
    let header = if applications.is_empty() {
        "no application class in the module: every local class and every auto-configuration on the class path counts".to_string()
    } else {
        let apps: Vec<String> = applications.iter().map(|a| a.replace(['/', '$'], ".")).collect();
        let packages: Vec<String> = scan.iter().map(|p| p.replace('/', ".")).collect();
        format!("{} ({}), scanning {}", apps.join(", "), if boot { "@SpringBootApplication" } else { "@ComponentScan" }, packages.join(", "))
    };
    Ok(Some(Bean { annotations: header, members }))
}

/// What meets a need (`Ok`), or why nothing does (`Err`).
fn resolve(walk: &Walk, local: &BTreeMap<&str, (Vec<Annotation>, Vec<Annotation>)>, out_of_scope: &BTreeMap<String, String>, need: Need) -> Result<Result<String, String>, Error> {
    match need {
        Need::Enable(switches) => {
            let mut best: Option<(String, &Place)> = None;
            let mut inactive: Option<(String, &Place)> = None;
            let mut unset: Option<(String, &str, &Place)> = None;
            for (name, element) in switches {
                for (annotation, place) in walk.enables.get(*name).map(Vec::as_slice).unwrap_or_default() {
                    let what = render_switch(name, *element);
                    if !satisfies(annotation, *element) {
                        if unset.is_none() {
                            unset = Some((format!("@{}", simple_name_of(name)), element.map_or("", |(e, _)| e), place));
                        }
                        continue;
                    }
                    if place.inactive.is_some() {
                        if inactive.is_none() {
                            inactive = Some((what, place));
                        }
                        continue;
                    }
                    if best.as_ref().is_none_or(|(_, b)| place.rank() < b.rank()) {
                        best = Some((what, place));
                    }
                }
            }
            if let Some((what, place)) = best {
                return Ok(Ok(format!("{what} on {}", place.render())));
            }
            let (first, element) = switches[0];
            let mut reason = format!("no {} on a configuration in scope", render_switch(first, element));
            // The nearest miss: a local class that carries the switch but is out of scope (and not reached another
            // way), then a configuration whose condition fails, then one with the switch but not its element.
            let nearby = local.iter().filter(|(name, _)| out_of_scope.contains_key(**name) && !walk.visited.contains(**name)).find_map(|(name, (_, expanded))| {
                let found = expanded.iter().find(|a| switches.iter().any(|(s, e)| a.type_name == *s && satisfies(a, *e)))?;
                Some((format!("@{}", found.simple_name()), name.replace(['/', '$'], "."), out_of_scope[*name].clone()))
            });
            if let Some((what, name, why)) = nearby {
                reason.push_str(&format!(" ({name} has {what}, but {why})"));
            } else if let Some((what, place)) = inactive {
                reason.push_str(&format!(" ({} has {what}, but {})", place.render().split(", ").next().unwrap_or_default(), place.inactive.as_deref().unwrap_or_default()));
            } else if let Some((what, element, place)) = unset {
                reason.push_str(&format!(" ({} has {what}, but not {element} = true)", place.render().split(", ").next().unwrap_or_default()));
            }
            Ok(Err(reason))
        }
        Need::Bean(ty) => {
            let places = walk.beans.get(ty).map(Vec::as_slice).unwrap_or_default();
            let simple = simple_name_of(ty);
            if let Some(place) = places.iter().filter(|p| p.inactive.is_none()).min_by_key(|p| p.rank()) {
                return Ok(Ok(format!("{simple} bean on {}", place.render())));
            }
            let mut reason = format!("no {simple} bean on a configuration in scope");
            if let Some(place) = places.first() {
                reason.push_str(&format!(" ({} defines one, but {})", place.render().split(", ").next().unwrap_or_default(), place.inactive.as_deref().unwrap_or_default()));
            }
            Ok(Err(reason))
        }
        Need::Provider => {
            for resource in PROVIDERS {
                if let Some((entry, bytes)) = walk.cp.resources(resource)?.into_iter().next() {
                    let provider = String::from_utf8_lossy(&bytes).lines().map(|l| l.split('#').next().unwrap_or("").trim().to_string()).find(|l| !l.is_empty()).unwrap_or_else(|| "a provider".to_string());
                    let entry = entry.rsplit(['/', '\\']).next().unwrap_or(&entry).to_string();
                    return Ok(Ok(format!("Bean Validation provider {provider} in {entry}")));
                }
            }
            Ok(Err("no Bean Validation provider on the class path (spring-boot-starter-validation adds Hibernate Validator)".to_string()))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn annotation(type_name: &str, elements: Vec<(&str, ElementValue)>) -> Annotation {
        Annotation { type_name: type_name.to_string(), elements: elements.into_iter().map(|(n, v)| (n.to_string(), v)).collect() }
    }

    #[test]
    fn a_switch_with_an_element_counts_when_set_or_defaulted_true() {
        let bare = annotation(ENABLE_METHOD_SECURITY, vec![]);
        assert!(satisfies(&bare, Some(("prePostEnabled", true))));
        assert!(!satisfies(&bare, Some(("securedEnabled", false))));
        let secured = annotation(ENABLE_METHOD_SECURITY, vec![("securedEnabled", ElementValue::Boolean(true))]);
        assert!(satisfies(&secured, Some(("securedEnabled", false))));
        let off = annotation(ENABLE_METHOD_SECURITY, vec![("prePostEnabled", ElementValue::Boolean(false))]);
        assert!(!satisfies(&off, Some(("prePostEnabled", true))));
        assert_eq!(render_switch(ENABLE_METHOD_SECURITY, Some(("securedEnabled", false))), "@EnableMethodSecurity(securedEnabled = true)");
        assert_eq!(render_switch(ENABLE_METHOD_SECURITY, Some(("prePostEnabled", true))), "@EnableMethodSecurity");
    }

    #[test]
    fn spring_factories_values_continue_over_lines() {
        let text = "# comment\norg.springframework.boot.autoconfigure.EnableAutoConfiguration=\\\n  com.a.AutoA,\\\n  com.a.AutoB\nother.key=x\n";
        assert_eq!(factories_value(text, FACTORIES_KEY), vec!["com.a.AutoA", "com.a.AutoB"]);
        assert_eq!(factories_value("k=a, b", "k"), vec!["a", "b"]);
    }

    #[test]
    fn places_render_by_how_they_are_reached() {
        let auto = Place { class: "org/springframework/boot/kafka/autoconfigure/KafkaAnnotationDrivenConfiguration$EnableKafkaConfiguration".into(), how: How::AutoConfigured, inactive: None };
        assert_eq!(auto.render(), "KafkaAnnotationDrivenConfiguration.EnableKafkaConfiguration, auto-configured");
        let imported = Place { class: "a/b/Shared$Inner".into(), how: How::Imported("a/App".into()), inactive: None };
        assert_eq!(imported.render(), "a.b.Shared.Inner, imported by App");
        assert_eq!(Place { class: "a/Local".into(), how: How::Local, inactive: None }.render(), "a.Local");
    }

    #[test]
    fn scan_packages_default_to_the_class_own() {
        let app = annotation(SPRING_BOOT_APPLICATION, vec![("scanBasePackages", ElementValue::Array(vec![ElementValue::String("com.x".into())]))]);
        assert_eq!(scan_packages("a/App", &[app]).into_iter().collect::<Vec<_>>(), vec!["com/x"]);
        assert_eq!(scan_packages("a/b/App", &[annotation(SPRING_BOOT_APPLICATION, vec![])]).into_iter().collect::<Vec<_>>(), vec!["a/b"]);
    }
}
