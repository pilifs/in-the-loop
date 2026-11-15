//! The cost tier a test runs at. Only the tests use it; `lib/tests/costs.json` lists every test's tier, and
//! `lib/README.md`'s Tests section says how to run each.
//!
//! - **unit**: in process, with no subprocess. Always runs.
//! - **tool**: spawns `javac`, `java`, the `jvmcontract` binary or a stand-in script. It runs by default, and is
//!   skipped under `JVMCONTRACT_TEST_TIER=unit`: such a test calls [`tool_tier!`](crate::tool_tier) first.
//! - **proof**: JBMC, TLC, or over the tool tier's limits (10 s, 1 GB). Ignored, with a reason
//!   `cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST`, and run as a pipeline job. A proof-tier test that still runs by
//!   default (`retier: pending` in the inventory) calls `tool_tier!(pending)` first, so the unit-only run skips it
//!   too, until a later change moves it to the proof tier.
//!
//! Without the variable, nothing is skipped.

/// The environment variable that picks the tiers a run includes.
pub const VARIABLE: &str = "JVMCONTRACT_TEST_TIER";

/// Whether this run skips the tool tier: `JVMCONTRACT_TEST_TIER=unit`. Unset, empty, `tool` and `proof` include it.
/// Any other value panics, so that a misspelt tier fails the run instead of running everything.
pub fn unit_only() -> bool {
    unit_only_under(std::env::var(VARIABLE).ok().as_deref())
}

fn unit_only_under(value: Option<&str>) -> bool {
    match value {
        None | Some("" | "tool" | "proof") => false,
        Some("unit") => true,
        Some(other) => panic!("{VARIABLE}={other:?}: the tiers are unit, tool and proof"),
    }
}

/// What [`tool_tier!`](crate::tool_tier) calls: whether to skip, saying so on stderr when it does.
#[doc(hidden)]
pub fn skip(tier: &str) -> bool {
    let skip = unit_only();
    if skip {
        eprintln!("skipped: {tier} test, under {VARIABLE}=unit");
    }
    skip
}

/// The first statement of a tool-tier test: returns from it under `JVMCONTRACT_TEST_TIER=unit`. A test the inventory
/// lists as `retier: pending` (proof tier by what it calls or took, but still run by default) calls
/// `tool_tier!(pending)` instead.
#[macro_export]
macro_rules! tool_tier {
    () => {
        if $crate::test_tier::skip("a tool-tier") {
            return;
        }
    };
    (pending) => {
        if $crate::test_tier::skip("a proof-tier (retier pending)") {
            return;
        }
    };
}

#[cfg(test)]
mod tests {
    use super::unit_only_under;

    #[test]
    fn only_the_unit_tier_skips_the_tool_tier() {
        assert!(unit_only_under(Some("unit")));
        for value in [None, Some(""), Some("tool"), Some("proof")] {
            assert!(!unit_only_under(value), "{value:?}");
        }
    }

    #[test]
    #[should_panic(expected = "the tiers are unit, tool and proof")]
    fn a_misspelt_tier_fails_the_run() {
        unit_only_under(Some("units"));
    }
}
