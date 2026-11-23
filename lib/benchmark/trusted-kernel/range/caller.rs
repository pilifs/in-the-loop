use super::*;

#[derive(Clone, Copy, PartialEq)]
enum Roots {
    SharedInside,
    SharedOutside,
    Distinct,
}
impl Roots {
    fn observation(self) -> Term {
        if self == Self::SharedInside {
            Value
        } else {
            OldOther
        }
    }
    fn key(self) -> &'static str {
        match self {
            Self::SharedInside => "shared-in-range",
            Self::SharedOutside => "shared-outside-range",
            Self::Distinct => "distinct-root",
        }
    }
}

// Abstract calls and concrete refutations both use the independently proved fill frame.
// Concrete controls have a valid [0,0), value 7 and k=0 in the observed root.
struct Concrete {
    primary: Vec<i32>,
    other: Option<Vec<i32>>,
}
impl Concrete {
    fn cells(&self, root: Term) -> Result<&[i32]> {
        match root {
            Root => Ok(&self.primary),
            Other => self
                .other
                .as_deref()
                .ok_or_else(|| unsupported("unbound distinct witness root")),
            _ => Err(unsupported("witness array reference")),
        }
    }
}
enum Domain {
    Universal {
        roots: Roots,
        at_length: bool,
        filled: bool,
    },
    Concrete(Concrete),
}
impl Domain {
    fn args(&self) -> [Term; 6] {
        match self {
            Self::Universal { .. } => [Root, Other, From, To, Value, K],
            Self::Concrete(heap) => [
                Root,
                if heap.other.is_some() { Other } else { Root },
                Int(0),
                Int(0),
                Int(7),
                Int(0),
            ],
        }
    }
    fn length(&self, root: Term) -> Result<Term> {
        match (self, root) {
            (Self::Universal { .. }, Root) => Ok(Length),
            (Self::Concrete(heap), r) => Ok(Int(heap.cells(r)?.len() as i32)),
            _ => Err(unsupported("length of untracked caller root")),
        }
    }
    fn branch(&self, args: [Term; 2], test: Test) -> Result<bool> {
        if let Self::Universal { at_length, .. } = self {
            if args == [To, Length] || args == [Length, To] {
                let order = if *at_length { Equal } else { Less };
                return Ok(test.value(if args[0] == To {
                    order
                } else {
                    order.reverse()
                }));
            }
        }
        branch(args, test, Phase::Entry)
    }
    fn add(&self, a: Term, b: Term) -> Result<Term> {
        match (self, a, b) {
            (_, Int(x), Int(y)) => Ok(Int(x.wrapping_add(y))),
            (
                Self::Universal {
                    at_length: false, ..
                },
                To,
                Int(1),
            ) => Ok(Next),
            _ => Err(unsupported("caller integer addition")),
        }
    }
    fn fill(&mut self, args: [Term; 4], pc: usize) -> Result<()> {
        match (self, args) {
            (Self::Universal { filled, .. }, [Root, From, To, Value]) => *filled = true,
            (Self::Concrete(heap), [Root, Int(lo), Int(hi), Int(value)]) => {
                let changed = heap
                    .primary
                    .get_mut(lo as usize..hi as usize)
                    .ok_or_else(|| unsupported("witness callee range outside precondition"))?;
                changed.fill(value);
            }
            _ => {
                return Err(unsupported(format!(
                    "callee write interval or arguments at {pc}: {args:?}"
                )))
            }
        }
        Ok(())
    }
    fn read(&self, root: Term, k: Term) -> Result<Option<Term>> {
        match self {
            Self::Concrete(heap) => {
                let Int(k) = k else {
                    return Err(unsupported("witness index"));
                };
                Ok(heap.cells(root)?.get(k as usize).copied().map(Int))
            }
            Self::Universal { roots, filled, .. }
                if k == K && (root == Other || (root == Root && *roots != Roots::Distinct)) =>
            {
                Ok(Some(if *filled {
                    roots.observation()
                } else {
                    OldOther
                }))
            }
            _ => Err(unsupported(
                "caller read needs a valid index in the observed root",
            )),
        }
    }
}

enum Exit {
    Return(Term),
    Bounds(usize),
}

fn run(
    class: &Class,
    callee: &Class,
    req: &Request,
    m: &Code,
    domain: &mut Domain,
    keys: &mut Obligations,
) -> Result<Exit> {
    let mut frame = Frame::new(m, &domain.args())?;
    let mut pc = 0;
    let mut seen = BTreeSet::new();
    loop {
        if !seen.insert(pc) {
            return Err(unsupported(format!("caller cycle at {pc}")));
        }
        let (op, mut next) = instruction(m.bytes, pc)?;
        let edge = next.to_string();
        if !frame.local_step(op)? {
            match op {
                Op::Length => {
                    let [root] = frame.pop()?;
                    frame.stack.push(domain.length(root)?);
                    obligation(keys, m, pc, &edge, "nonnull");
                }
                Op::Add => {
                    let [a, b] = frame.pop()?;
                    frame.stack.push(domain.add(a, b)?);
                }
                Op::If(test, pair, dest) => {
                    if domain.branch(frame.operands(pair)?, test)? {
                        next = dest;
                    }
                }
                Op::Goto(dest) => next = dest,
                Op::Call(i) => {
                    if class.method_ref(i)? != (callee.owner, req.companion.0, FILL_DESC) {
                        return Err(unsupported(format!("external fill resolution at {pc}")));
                    }
                    domain.fill(frame.pop()?, pc)?;
                    obligation(keys, m, pc, &edge, "apply-checked-write-frame");
                }
                Op::Read(Element::Int) => {
                    let [root, k] = frame.pop()?;
                    let Some(value) = domain.read(root, k)? else {
                        return Ok(Exit::Bounds(pc));
                    };
                    frame.stack.push(value);
                    if let Domain::Universal { roots, .. } = domain {
                        obligation(keys, m, pc, &edge, roots.key());
                    }
                }
                Op::Return => {
                    let [v] = frame.pop()?;
                    if !frame.stack.is_empty() {
                        return Err(unsupported("caller return stack"));
                    }
                    if let Domain::Universal { roots, filled, .. } = domain {
                        if !*filled || v != roots.observation() {
                            return Err(reject(format!("caller frame or observation at {pc}")));
                        }
                        obligation(keys, m, pc, "exit", "exact-write-frame");
                        obligation(keys, m, pc, "exit", "observation");
                    }
                    return Ok(Exit::Return(v));
                }
                _ => return Err(unsupported(format!("caller rule {op:?} at {pc}"))),
            }
        }
        obligation(keys, m, pc, &next.to_string(), "step");
        pc = next;
    }
}

fn refutation(class: &Class, callee: &Class, req: &Request, m: &Code) -> Option<String> {
    for (label, primary, other, expected) in [
        ("shared [11]", vec![11], None, 11),
        ("distinct a=[] other=[31]", vec![], Some(vec![31]), 31),
    ] {
        let mut domain = Domain::Concrete(Concrete {
            primary: primary.clone(),
            other,
        });
        let exit = run(class, callee, req, m, &mut domain, &mut Obligations::new());
        let Domain::Concrete(heap) = domain else {
            unreachable!()
        };
        let why = match exit {
            Ok(Exit::Bounds(pc)) => {
                format!("array bounds exception at read {pc}, expected normal return {expected}")
            }
            Ok(Exit::Return(Int(v))) if v != expected || heap.primary != primary => {
                format!(
                    "returned {v}, after {:?}, expected {expected} and {primary:?}",
                    heap.primary
                )
            }
            _ => continue,
        };
        return Some(format!(
            "checked witness {label}, from=0 to=0 value=7 k=0: {why}"
        ));
    }
    None
}

pub(super) fn check(
    class: &Class,
    callee: &Class,
    req: &Request,
    keys: &mut Obligations,
) -> Result<()> {
    if req.entry.1 != "([I[IIIII)I" {
        return Err(unsupported("range caller descriptor"));
    }
    let m = class.method(req.entry.0, req.entry.1, true)?;
    for roots in [Roots::SharedInside, Roots::SharedOutside, Roots::Distinct] {
        for at_length in [true, false] {
            let mut domain = Domain::Universal {
                roots,
                at_length,
                filled: false,
            };
            match run(class, callee, req, m, &mut domain, keys) {
                Ok(Exit::Return(_)) => (),
                Ok(Exit::Bounds(pc)) => return Err(reject(format!("caller bounds at {pc}"))),
                Err(first) => {
                    return Err(match refutation(class, callee, req, m) {
                        Some(why) => reject(format!("{why}; first rule: {}", first.1)),
                        None => first,
                    })
                }
            }
        }
    }
    Ok(())
}
