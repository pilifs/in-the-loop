import Lean

namespace RangeRule

inductive Phase | guard | entry | exhausted | iteration deriving DecidableEq, Repr
inductive Term | zero | lo | cursor | hi | len deriving DecidableEq, Repr
inductive Test | eq | ne | lt | ge | gt | le deriving DecidableEq, Repr

def term (lo i hi n : Int) : Term → Int
  | .zero => 0
  | .lo => lo
  | .cursor => i
  | .hi => hi
  | .len => n

def compare (t : Test) (x y : Int) : Prop :=
  match t with
  | .eq => x = y | .ne => x ≠ y | .lt => x < y
  | .ge => x ≥ y | .gt => x > y | .le => x ≤ y

def admitted (p : Phase) (lo i hi n : Int) : Prop :=
  0 ≤ lo ∧ lo ≤ i ∧ i ≤ hi ∧ hi ≤ n ∧ n ≤ 2147483647 ∧
  (p = .exhausted → i = hi) ∧ (p = .iteration → i < hi)

def sound (p : Phase) (x y : Term) (test : Test) (answer : Bool) : Prop :=
  ∀ lo i hi n : Int, admitted p lo i hi n →
    (compare test (term lo i hi n x) (term lo i hi n y) ↔ answer = true)

-- This decoder is deliberately limited to the bytes of the two JDK forward loop
-- bodies, from the guard at PC 10 through the exit. Both relative branch offsets
-- are checked: at PC 13 +14 reaches the return, and at PC 24 -14 reaches the cut.
def forwardBody (wide : Bool) (code : List Nat) : Bool :=
  let slot := if wide then 5 else 4
  let valueLoad := if wide then 33 else 29   -- lload_3 / iload_3
  let store := if wide then 80 else 79       -- lastore / iastore
  code.drop 10 == [21,slot,28,162,0,14,42,21,slot,valueLoad,store,132,slot,1,167,255,242,177]

def prefixFrame (old now : Int → α) (lo i : Int) (v : α) : Prop :=
  ∀ k, now k = if lo ≤ k ∧ k < i then v else old k

def write (h : Int → α) (i : Int) (v : α) : Int → α :=
  fun k => if k = i then v else h k

def inc32 (i : Int) : Int := if i = 2147483647 then -2147483648 else i + 1

-- One iteration as decoded in forwardBody. The entry state supplies the valid
-- range, fetched root, cursor and the original full-width argument in local 3.
def step (wide : Bool) (code : List Nat) (h : Int → α) (i : Int) (v : α) :
    Option ((Int → α) × Int) :=
  if forwardBody wide code then some (write h i v, inc32 i) else none

theorem iteration (wide : Bool) (code : List Nat) (decoded : forwardBody wide code = true)
    (old now : Int → α) (v : α) (lo i hi n : Int)
    (valid : admitted .iteration lo i hi n) (pre : prefixFrame old now lo i v) :
    ∃ after j, step wide code now i v = some (after, j) ∧ prefixFrame old after lo j v ∧
      j = i + 1 ∧ j ≤ 2147483647 ∧ 0 ≤ hi - j ∧ hi - j < hi - i := by
  simp [admitted] at valid
  have fresh : i ≠ 2147483647 := by omega
  refine ⟨write now i v, i + 1, ?_, ?_, rfl, ?_, ?_, ?_⟩
  · simp [step, decoded, inc32, fresh]
  · intro k
    by_cases same : k = i
    · subst k
      have inside : lo ≤ i ∧ i < i + 1 := by omega
      simp [write, inside]
    · by_cases inRange : lo ≤ k ∧ k < i
      · have extended : lo ≤ k ∧ k < i + 1 := by omega
        simp [write, same, pre k, inRange, extended]
      · have outside : ¬(lo ≤ k ∧ k < i + 1) := by omega
        simp [write, same, pre k, inRange, outside]
  all_goals omega

end RangeRule
