import Lean

namespace ArrayReverse

abbrev Heap (α : Type) := Int → α

-- Bytecode writes the low cell to the high index, then the saved high cell to
-- the low index. Every reference to the array observes the same final heap.
def swap (h : Heap α) (i j k : Int) : α :=
  if k = i then h j else if k = j then h i else h k

def frame (old : Heap α) (lo hi k : Int) : α :=
  if lo ≤ k ∧ k < hi then old (lo + hi - 1 - k) else old k

def invariant (old h : Heap α) (lo hi i j : Int) : Prop :=
  i + j = lo + hi - 1 ∧ lo ≤ i ∧ j < hi ∧
  ∀ k, h k = if lo ≤ k ∧ k < hi ∧ (k < i ∨ j < k) then old (lo + hi - 1 - k) else old k

theorem advance (old h : Heap α) (lo hi i j : Int)
    (before : invariant old h lo hi i j) (lt : i < j) :
    invariant old (swap h i j) lo hi (i + 1) (j - 1) := by
  obtain ⟨balance, left, right, cells⟩ := before
  refine ⟨by omega, by omega, by omega, ?_⟩
  have atI : h i = old i := by
    simpa only [ite_eq_right (show ¬ (lo ≤ i ∧ i < hi ∧ (i < i ∨ j < i)) by omega)] using cells i
  have atJ : h j = old j := by
    simpa only [ite_eq_right (show ¬ (lo ≤ j ∧ j < hi ∧ (j < i ∨ j < j)) by omega)] using cells j
  intro k
  by_cases isI : k = i
  · subst k
    have covered : lo ≤ i ∧ i < hi ∧ (i < i + 1 ∨ j - 1 < i) := by omega
    simp [swap, covered, atJ, show lo + hi - 1 - i = j by omega]
  by_cases isJ : k = j
  · subst k
    have covered : lo ≤ j ∧ j < hi ∧ (j < i + 1 ∨ j - 1 < j) := by omega
    simp [swap, isI, covered, atI, show lo + hi - 1 - j = i by omega]
  have same : (lo ≤ k ∧ k < hi ∧ (k < i + 1 ∨ j - 1 < k)) ↔
      (lo ≤ k ∧ k < hi ∧ (k < i ∨ j < k)) := by omega
  simpa only [swap, ite_eq_right isI, ite_eq_right isJ, propext same] using cells k

theorem finished (old h : Heap α) (lo hi i j : Int)
    (before : invariant old h lo hi i j) (done : j ≤ i) :
    ∀ k, h k = frame old lo hi k := by
  obtain ⟨balance, _, _, cells⟩ := before
  intro k
  by_cases inside : lo ≤ k ∧ k < hi
  · by_cases outside : k < i ∨ j < k
    · simpa [frame, inside, outside] using cells k
    · have middle : lo + hi - 1 - k = k := by omega
      simpa [frame, inside, outside, middle] using cells k
  · have outside : ¬ (lo ≤ k ∧ k < hi ∧ (k < i ∨ j < k)) := by omega
    simpa only [frame, ite_eq_right inside, ite_eq_right outside] using cells k

def safe (n i j : Int) : Prop :=
  0 ≤ i ∧ i < n ∧ 0 ≤ j ∧ j < n ∧ i + 1 ≤ 2147483647 ∧ -2147483648 ≤ j - 1

instance (n i j : Int) : Decidable (safe n i j) := by unfold safe; infer_instance

inductive Operand (α : Type)
  | array
  | index (k : Int)
  | cell (v : α)

-- Execute the straight-line instructions from PCs 27 through 44. Local 3 is the
-- low cursor, 4 the high cursor and 5 the saved cell. The caller checks their bounds.
def executeStores (i j : Int) : List Nat → List (Operand α) → Option α → Heap α → Option (Heap α)
  | [], [], _, h => some h
  | 42 :: b, s, t, h => executeStores i j b (.array :: s) t h
  | 21 :: 4 :: b, s, t, h => executeStores i j b (.index j :: s) t h
  | 21 :: 3 :: b, s, t, h => executeStores i j b (.index i :: s) t h
  | 29 :: b, s, t, h => executeStores i j b (.index i :: s) t h
  | 46 :: b, .index k :: .array :: s, t, h => executeStores i j b (.cell (h k) :: s) t h
  | 54 :: 5 :: b, .cell v :: s, _, h => executeStores i j b s (some v) h
  | 21 :: 5 :: b, s, some t, h => executeStores i j b (.cell t :: s) (some t) h
  | 79 :: b, .cell v :: .index k :: .array :: s, t, h =>
      executeStores i j b s t (fun x => if x = k then v else h x)
  | _, _, _, _ => none

def releaseStores : List Nat := [42,21,4,46,54,5,42,21,4,42,29,46,79,42,29,21,5,79]

theorem releaseSwap (h : Heap α) (i j : Int) :
    executeStores i j releaseStores [] none h = some (swap h i j) := by rfl

def run (stores : List Nat) : Nat → Int → Int → Int → Heap α → Option (Heap α)
  | 0, _, i, j, h => if i < j then none else some h
  | fuel + 1, n, i, j, h =>
      if i < j then
        if safe n i j then do
          let after ← executeStores i j stores [] none h
          run stores fuel n (i + 1) (j - 1) after
        else none
      else some h

theorem boundedLoop (fuel : Nat) (old : Heap α) (lo hi n : Int)
    (bounds : 0 ≤ lo ∧ lo ≤ hi ∧ hi ≤ n ∧ n ≤ 2147483647) :
    ∀ i j h, invariant old h lo hi i j → j - i ≤ (fuel : Int) →
      ∃ out, run releaseStores fuel n i j h = some out ∧ ∀ k, out k = frame old lo hi k := by
  induction fuel with
  | zero =>
    intro i j h inv enough
    have done : ¬ i < j := by omega
    exact ⟨h, by simp [run, done], finished old h lo hi i j inv (by omega)⟩
  | succ fuel ih =>
    intro i j h inv enough
    by_cases lt : i < j
    · have ok : safe n i j := by
        obtain ⟨_, left, right, _⟩ := inv
        unfold safe
        omega
      obtain ⟨out, evaluation, post⟩ := ih (i + 1) (j - 1) (swap h i j) (advance old h lo hi i j inv lt) (by omega)
      exact ⟨out, by simpa [run, lt, ok, releaseSwap] using evaluation, post⟩
    · exact ⟨h, by simp [run, lt], finished old h lo hi i j inv (by omega)⟩

-- The original int method has two calls, at PCs 7 and 14. The classfile
-- reader resolves their pool operands independently to the two bound Math bodies.
def releaseCode : List Nat :=
  [42,199,0,4,177,27,3,184,2,50,62,42,190,28,184,3,2,4,100,54,4,21,4,29,164,0,30] ++
  releaseStores ++ [132,4,255,132,3,1,167,255,226,177]

def decodeRelease (code maxBody minBody : List Nat) : Bool :=
  code == releaseCode &&
  maxBody == [26,27,161,0,7,26,167,0,4,27,172] && minBody == [26,27,163,0,7,26,167,0,4,27,172]

def decJava (x : Int) : Int := if x = -2147483648 then 2147483647 else x - 1

def execute (code maxBody minBody : List Nat) (old : Heap α) (lo hi n : Int) : Option (Heap α) :=
  if decodeRelease code maxBody minBody then
    run ((code.drop 27).take 18) n.toNat n (max lo 0) (decJava (min n hi)) old
  else none

theorem reverseValid (code maxBody minBody : List Nat) (bound : decodeRelease code maxBody minBody = true)
    (old : Heap α) (lo hi n : Int) (bounds : 0 ≤ lo ∧ lo ≤ hi ∧ hi ≤ n ∧ n ≤ 2147483647) :
    ∃ out, execute code maxBody minBody old lo hi n = some out ∧ ∀ k, out k = frame old lo hi k := by
  have init : invariant old old lo hi lo (hi - 1) := by
    refine ⟨by omega, by omega, by omega, ?_⟩
    intro k
    simp [show ¬ (lo ≤ k ∧ k < hi ∧ (k < lo ∨ hi - 1 < k)) by omega]
  have low : max lo 0 = lo := Int.max_eq_left (by omega)
  have high : min n hi = hi := Int.min_eq_right (by omega)
  have normal : hi ≠ -2147483648 := by omega
  have body : (code.drop 27).take 18 = releaseStores := by
    by_cases same : code = releaseCode
    · rw [same]; rfl
    · simp [decodeRelease, same] at bound
  simpa [execute, bound, body, low, high, decJava, normal] using
    (boundedLoop n.toNat old lo hi n bounds lo (hi - 1) old init (by omega))

end ArrayReverse
