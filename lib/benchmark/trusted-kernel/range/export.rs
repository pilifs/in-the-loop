//! Test-only export of the *compiled* decision rule and the actual method's checked edges.
use super::*;

#[test]
fn export() {
    let terms = [("zero", Int(0)), ("lo", From), ("cursor", Cursor), ("hi", To), ("len", Length)];
    let tests = [("eq", Test::Eq), ("ne", Test::Ne), ("lt", Test::Lt), ("ge", Test::Ge),
                 ("gt", Test::Gt), ("le", Test::Le)];
    for (p, phase) in [("guard", Phase::Guard), ("entry", Phase::Entry),
                       ("exhausted", Phase::Exhausted), ("iteration", Phase::Iteration)] {
        for (x, a) in terms {
            for (y, b) in terms {
                for (name, test) in tests {
                    let answer = match branch([a, b], test, phase) {
                        Ok(true) => "true", Ok(false) => "false", Err(_) => "open",
                    };
                    println!("DECISION {p} {x} {y} {name} {answer}");
                }
            }
        }
    }
    let bytes = std::fs::read("Arrays.class").unwrap();
    let class = Class::parse(&bytes).unwrap();
    let pin = crate::digest::sha256_hex(&bytes);
    for (descriptor, slot) in [(FILL_DESC, 4), ("([JIIJ)V", 5)] {
        let method = class.method("fill", descriptor, true).unwrap();
        let body: String = method.bytes.iter().map(|b| format!("{b:02x}")).collect();
        let request = format!("request 1\ntheorem {DIRECT}\nenvironment initialized-verified-jvm-v1\nclass {} {}\nentry fill {descriptor}\ncompanion rangeCheck (III)V\n", class.owner, pin);
        let req = crate::parse_request(&request).unwrap();
        let mut keys = Obligations::new();
        match check(&class, None, &req, &format!("hints written-prefix remaining 10 {slot}"), &mut keys) {
            Ok(()) => {
                for key in ["20>21 in-bounds-prefix-store", "21>24 no-signed-overflow",
                            "24>10 extend-written-prefix", "24>10 variant-decreases"] {
                    assert!(keys.contains(&format!("fill{descriptor}@{key}")));
                }
                println!("EDGE {descriptor} {slot} {body} accepted {} {pin}", keys.len());
            }
            Err(e) => println!("EDGE {descriptor} {slot} {body} {} {}", e.0, e.1),
        }
    }
}
