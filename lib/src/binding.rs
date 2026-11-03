//! Request binding checks: whether a handler's parameters can bind to the request. Spring resolves a `@PathVariable`,
//! `@RequestParam`, `@RequestHeader`, `@CookieValue` or `@MatrixVariable` at request time, by a name it takes from the
//! annotation or from the bytecode, so a mismatch is not a compile error and not a startup failure but a 500 on every
//! request of the route: a `@PathVariable` whose name is in no template of the route
//! (`MissingPathVariableException`), a name the compiler did not record (Spring 6.1 reads the `MethodParameters`
//! attribute only, which `javac -parameters` writes), and an optional parameter of a primitive type, which cannot be
//! null when the request leaves it out. Two handlers on one route are found across the module: the same mapping twice
//! fails the context at startup, and the same pattern under different variable names is an ambiguity every request
//! that matches hits.

use std::collections::{BTreeMap, BTreeSet};

use crate::classfile::{Annotation, MethodDescriptor, Type};

/// The annotations that bind a parameter by name.
const NAMED: &[&str] = &["PathVariable", "RequestParam", "RequestHeader", "CookieValue", "MatrixVariable", "RequestPart", "RequestAttribute", "SessionAttribute"];

/// The name an annotation binds, from its `value` or `name` element.
fn explicit_name(a: &Annotation) -> Option<String> {
    a.strings("value").into_iter().chain(a.strings("name")).find(|s| !s.is_empty())
}

/// The path of a rendered route (`GET /orders/{id} (consumes application/json)` is `/orders/{id}`).
fn path_of(route: &str) -> &str {
    route.split_whitespace().nth(1).unwrap_or(route)
}

/// The variables of a route's path: `{id}` and `{id:\d+}` are `id`, `{*rest}` is `rest`.
pub(crate) fn template_variables(route: &str) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let path = path_of(route);
    let mut rest = path;
    while let Some(start) = rest.find('{') {
        let Some(len) = rest[start..].find('}') else { break };
        let inner = &rest[start + 1..start + len];
        let name = inner.split(':').next().unwrap_or(inner).trim_start_matches('*');
        if !name.is_empty() {
            out.insert(name.to_string());
        }
        rest = &rest[start + len + 1..];
    }
    out
}

/// The route with its variable names removed (`GET /orders/{}`): two routes with one key match the same requests
/// with the same specificity, so Spring cannot choose between their handlers.
pub(crate) fn pattern_key(route: &str) -> String {
    let mut out = String::new();
    let mut depth = 0usize;
    for c in route.chars() {
        match c {
            '{' => {
                if depth == 0 {
                    out.push('{');
                }
                depth += 1;
            }
            '}' => {
                depth = depth.saturating_sub(1);
                if depth == 0 {
                    out.push('}');
                }
            }
            _ if depth > 0 => {}
            _ => out.push(c),
        }
    }
    out
}

/// A type a binder fills with every value rather than one by name.
fn takes_all(t: &Type) -> bool {
    matches!(t, Type::Object(c) if c == "java/util/Map" || c == "org/springframework/util/MultiValueMap" || c == "org/springframework/http/HttpHeaders")
}

/// The `!` lines for one handler: `routes` as rendered under the member, `types` and `names` as shown in the signature,
/// `reflective` the names the `MethodParameters` attribute records (what Spring sees), `parameter_annotations`
/// the framework annotations of each parameter.
pub(crate) fn check(routes: &[String], d: &MethodDescriptor, types: &[String], names: &[String], reflective: Option<&[String]>, parameter_annotations: &[Vec<Annotation>]) -> Vec<String> {
    let mut out = Vec::new();
    let mut bodies = 0;
    for (i, list) in parameter_annotations.iter().enumerate() {
        let Some(t) = d.params.get(i) else { continue };
        let shown = names.get(i).cloned().unwrap_or_else(|| format!("arg{i}"));
        bodies += usize::from(list.iter().any(|a| a.simple_name() == "RequestBody"));
        for a in list.iter().filter(|a| NAMED.contains(&a.simple_name().as_str())) {
            let kind = a.simple_name();
            let name = match explicit_name(a) {
                Some(n) => Some(n),
                None if takes_all(t) => None,
                None => match reflective.and_then(|r| r.get(i)) {
                    Some(n) => Some(n.clone()),
                    None => {
                        out.push(format!("! @{kind} {shown}: the parameter's name is not in the bytecode (no MethodParameters attribute: compile with -parameters, or name it in the annotation), and Spring 6.1 reads nothing else, so the request fails with a 500"));
                        continue;
                    }
                },
            };
            if kind == "PathVariable" {
                if let Some(name) = &name {
                    let missing: Vec<&str> = routes.iter().map(|r| path_of(r)).filter(|r| !template_variables(r).contains(name)).collect::<BTreeSet<_>>().into_iter().collect();
                    if !missing.is_empty() {
                        out.push(format!("! @PathVariable {name} matches no variable in {}: MissingPathVariableException, a 500 on every request", missing.join(", ")));
                    }
                }
            }
            let optional = a.element("required").is_some_and(|v| v.render() == "false") && a.element("defaultValue").is_none();
            if optional && !matches!(t, Type::Object(_) | Type::Array(_) | Type::Void) {
                out.push(format!("! @{kind}(required = false) on {} {shown}: a primitive cannot be null, so a request without it fails with a 500 instead of a 400", types.get(i).map_or("", String::as_str)));
            }
        }
    }
    if bodies > 1 {
        out.push("! two @RequestBody parameters: the body is read once, so the second is always missing (a 400 on every request)".to_string());
    }
    out
}

/// The `!` lines for a handler whose routes another handler of the module also claims. `handlers` maps each route's
/// pattern key to the labels of the handlers mapped to it, with the route as each was rendered.
pub(crate) fn clashes(routes: &[String], label: &str, handlers: &BTreeMap<String, Vec<(String, String)>>) -> Vec<String> {
    let mut out = Vec::new();
    for route in routes {
        let Some(others) = handlers.get(&pattern_key(route)) else { continue };
        for (other, other_route) in others.iter().filter(|(l, _)| l != label) {
            if other_route == route {
                out.push(format!("! {route} is also mapped to {other}: Spring refuses the duplicate, so the context does not start"));
            } else {
                out.push(format!("! {route} matches the same requests as {other_route} on {other}: neither is more specific, so every request that matches is ambiguous, a 500"));
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn variables_come_from_the_path_only() {
        let vars = template_variables("GET /a/{id}/b/{slug:[a-z]+}/{*rest} (consumes application/json)");
        assert_eq!(vars.into_iter().collect::<Vec<_>>(), vec!["id", "rest", "slug"]);
        assert!(template_variables("GET /plain").is_empty());
    }

    #[test]
    fn pattern_keys_drop_variable_names() {
        assert_eq!(pattern_key("GET /a/{id}/b"), "GET /a/{}/b");
        assert_eq!(pattern_key("GET /a/{id:\\d{3}}"), "GET /a/{}");
        assert_eq!(pattern_key("GET /a/{x}"), pattern_key("GET /a/{y}"));
        assert_ne!(pattern_key("GET /a/{x}"), pattern_key("GET /a/b"));
    }
}
