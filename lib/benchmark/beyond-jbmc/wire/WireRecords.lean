import Std.Tactic.BVDecide

namespace WireRecords

structure FourBytes where
  b0 : BitVec 8
  b1 : BitVec 8
  b2 : BitVec 8
  b3 : BitVec 8

def big (v : BitVec 32) : FourBytes :=
  ⟨v.extractLsb' 24 8, v.extractLsb' 16 8, v.extractLsb' 8 8, v.extractLsb' 0 8⟩
def little (v : BitVec 32) : FourBytes :=
  ⟨v.extractLsb' 0 8, v.extractLsb' 8 8, v.extractLsb' 16 8, v.extractLsb' 24 8⟩
def readBig (b : FourBytes) : BitVec 32 := b.b0 ++ b.b1 ++ b.b2 ++ b.b3
def readLittle (b : FourBytes) : BitVec 32 := b.b3 ++ b.b2 ++ b.b1 ++ b.b0
def reverseWord (v : BitVec 32) : BitVec 32 := readBig (little v)

theorem fourCompositions (v : BitVec 32) :
    readBig (big v) = v ∧ readLittle (little v) = v ∧
    readBig (little v) = reverseWord v ∧ readLittle (big v) = reverseWord v := by
  simp [readBig, readLittle, big, little, reverseWord]
  all_goals bv_decide

theorem compatible (v : BitVec 32) : reverseWord v = v ↔
    (big v).b0 = (big v).b3 ∧ (big v).b1 = (big v).b2 := by
  unfold reverseWord readBig little big
  bv_decide

def palindrome (high : BitVec 16) : BitVec 32 :=
  high ++ high.extractLsb' 0 8 ++ high.extractLsb' 8 8

theorem palindromeBijection (high : BitVec 16) (v : BitVec 32) :
    (palindrome high).extractLsb' 16 16 = high ∧
    reverseWord (palindrome high) = palindrome high ∧
    (reverseWord v = v → palindrome (v.extractLsb' 16 16) = v) := by
  unfold palindrome reverseWord readBig little
  bv_decide

theorem wrongIdentity : reverseWord (0x01020304 : BitVec 32) ≠ 0x01020304 := by decide

def readN (read : List UInt8 → Option (α × List UInt8)) :
    Nat → List UInt8 → Option (List α × List UInt8)
  | 0, bytes => some ([], bytes)
  | n+1, bytes => do
      let (x, rest) ← read bytes
      let (xs, suffix) ← readN read n rest
      return (x :: xs, suffix)

/-- A complete-record law that preserves the unused suffix composes for any finite count.
    Capacity and cursor arithmetic for a Java caller still need to establish this premise. -/
theorem finiteRecords (write : α → List UInt8) (read : List UInt8 → Option (β × List UInt8))
    (transform : α → β)
    (record : ∀ v tail, read (write v ++ tail) = some (transform v, tail))
    (xs : List α) (suffix : List UInt8) :
    readN read xs.length (xs.flatMap write ++ suffix) = some (xs.map transform, suffix) := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [readN, List.append_assoc, record, ih]

#print axioms fourCompositions
#print axioms compatible
#print axioms palindromeBijection
#print axioms wrongIdentity
#print axioms finiteRecords
end WireRecords
