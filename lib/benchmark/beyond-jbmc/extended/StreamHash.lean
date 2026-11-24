import Std.Tactic.BVDecide

namespace StreamHash
abbrev Word := BitVec 32
abbrev Byte := BitVec 8

inductive Pending where
 | zero
 | one (a : Byte)
 | two (a b : Byte)
 | three (a b c : Byte)

structure Core where
  digest : Word
  pending : Pending

def key (w : Word) : Word := (w * 0xcc9e2d51).rotateLeft 15 * 0x1b873593
@[irreducible] def block (h : Word) (a b c d : Byte) : Word :=
  (h ^^^ key (d ++ c ++ b ++ a)).rotateLeft 13 * 5 + 0xe6546b64

def push (s : Core) (v : Byte) : Core :=
  match s.pending with
  | .zero => ⟨s.digest,.one v⟩
  | .one a => ⟨s.digest,.two a v⟩
  | .two a b => ⟨s.digest,.three a b v⟩
  | .three a b c => ⟨block s.digest a b c v,.zero⟩

/-- Specification traversing complete little-endian blocks first, followed by at most three bytes. -/
def blocks (h : Word) : List Byte → Core
  | a::b::c::d::rest => blocks (block h a b c d) rest
  | [a,b,c] => ⟨h,.three a b c⟩
  | [a,b] => ⟨h,.two a b⟩
  | [a] => ⟨h,.one a⟩
  | [] => ⟨h,.zero⟩

theorem fold_blocks (xs : List Byte) (h : Word) : xs.foldl push ⟨h,.zero⟩ = blocks h xs := by
  induction h, xs using blocks.induct with
  | case1 h a b c d rest ih =>
    change rest.foldl push ⟨block h a b c d,.zero⟩ = blocks (block h a b c d) rest
    exact ih
  | case2 => rfl
  | case3 => rfl
  | case4 => rfl
  | case5 => rfl

def finalMix (h : Word) : Word :=
  let x := (h ^^^ (h >>> 16)) * 0x85ebca6b
  let y := (x ^^^ (x >>> 13)) * 0xc2b2ae35
  y ^^^ (y >>> 16)

def finish (s : Core) (count : Word) : Word :=
  let tail := match s.pending with
    | .zero => 0
    | .one a => key (a.zeroExtend 32)
    | .two a b => key ((b ++ a).zeroExtend 32)
    | .three a b c => key ((c ++ b ++ a).zeroExtend 32)
  finalMix (s.digest ^^^ tail ^^^ count)

structure State where
  core : Core
  count : Word

def start (h : Word) : State := ⟨⟨h,.zero⟩,0⟩
def add (s : State) (xs : List Byte) : State :=
  ⟨xs.foldl push s.core,s.count + BitVec.ofNat 32 xs.length⟩

theorem add_append (s : State) (xs ys : List Byte) : add (add s xs) ys = add s (xs ++ ys) := by
  simp [add,List.foldl_append,BitVec.ofNat_add,BitVec.add_assoc]

theorem all_partitions (s : State) (parts : List (List Byte)) :
    parts.foldl add s = add s parts.flatten := by
  induction parts generalizing s with
  | nil => simp [add]
  | cons xs rest ih => simp [ih,add_append]

def endValue (s : State) : Word := finish s.core s.count
def oneShot (xs : List Byte) (seed : Word) : Word := finish (blocks seed xs) (BitVec.ofNat 32 xs.length)

theorem arbitrary_stream (parts : List (List Byte)) (seed : Word) :
    endValue (parts.foldl add (start seed)) = oneShot parts.flatten seed := by
  rw [all_partitions]
  simp [endValue,add,start,oneShot,fold_blocks]

/-- Reinitialization forgets an arbitrary old digest, byte count and partial block. -/
def reset (_prior : State) (seed : Word) : State := start seed
theorem reset_stream (before : State) (parts : List (List Byte)) (seed : Word) :
    endValue (parts.foldl add (reset before seed)) = oneShot parts.flatten seed :=
  arbitrary_stream parts seed

theorem empty_negative_byte : oneShot [0xff] 0 = 0xfd6cf10d := by decide

#print axioms fold_blocks
#print axioms all_partitions
#print axioms arbitrary_stream
#print axioms reset_stream
#print axioms empty_negative_byte
end StreamHash
