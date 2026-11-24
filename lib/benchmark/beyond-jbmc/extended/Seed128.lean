import Std.Tactic.BVDecide
import Init.Data.Function

namespace Seed128
abbrev W := BitVec 64
abbrev Pair := W × W
open Function

theorem mul_inj (k inv : W) (valid : k*inv=1) : Injective (fun x : W => x*k) := by
  intro a b equal
  have h := congrArg (fun y : W => y*inv) equal
  simpa [BitVec.mul_assoc,valid] using h

theorem rot27 : Injective (fun x : W => x.rotateLeft 27) := by
  intro a b h
  bv_decide
theorem rot31 : Injective (fun x : W => x.rotateLeft 31) := by
  intro a b h
  bv_decide

def shiftXor (x : W) := x ^^^ (x >>> 33)
theorem shift_inj : Injective shiftXor := by
  have twice (x : W) : shiftXor (shiftXor x) = x := by unfold shiftXor; bv_decide
  intro a b equal
  simpa only [twice] using congrArg shiftXor equal

def component (k n : W) (rot : W → W) (other h : W) : W :=
  (rot (h ^^^ k) + other)*5 + n

theorem component_inj (k n other : W) (rot : W → W) (inject : Injective rot) :
    Injective (component k n rot other) := by
  intro a b h
  unfold component at h
  apply (BitVec.xor_left_inj k).mp
  apply inject
  apply (BitVec.add_left_inj other).mp
  apply mul_inj 5 0xcccccccccccccccd (by decide)
  exact (BitVec.add_left_inj n).mp h

def coupled (f g : W → W → W) (s : Pair) : Pair :=
  let x := f s.2 s.1
  (x,g x s.2)

theorem coupled_inj (f g : W → W → W) (hf : ∀ o, Injective (f o)) (hg : ∀ o, Injective (g o)) :
    Injective (coupled f g) := by
  rintro ⟨a,b⟩ ⟨c,d⟩ equal
  have first : f b a = f d c := congrArg Prod.fst equal
  have second : g (f b a) b = g (f d c) d := congrArg Prod.snd equal
  rw [← first] at second
  have same : b=d := hg _ second
  cases same
  have same : a=c := hf _ first
  cases same
  rfl

def step (s k : Pair) : Pair := coupled
  (component k.1 0x52dce729 (fun x => x.rotateLeft 27))
  (component k.2 0x38495ab5 (fun x => x.rotateLeft 31)) s

theorem step_inj (k : Pair) : Injective (fun s => step s k) :=
  coupled_inj _ _ (fun _ => component_inj _ _ _ _ rot27) (fun _ => component_inj _ _ _ _ rot31)

def addPair := coupled (fun other x => x+other) (fun other x => x+other)
theorem addPair_inj : Injective addPair :=
  coupled_inj _ _ (fun o _ _ h => (BitVec.add_left_inj o).mp h) (fun o _ _ h => (BitVec.add_left_inj o).mp h)

def avalanche (x : W) : W := shiftXor ((shiftXor ((shiftXor x)*0xff51afd7ed558ccd))*0xc4ceb9fe1a85ec53)
theorem avalanche_inj : Injective avalanche := by
  intro a b h
  exact shift_inj (mul_inj 0xff51afd7ed558ccd 0x4f74430c22a54005 (by decide) (shift_inj (mul_inj 0xc4ceb9fe1a85ec53 0x9cb4b2f8129337db (by decide) (shift_inj h))))

def finalPair (tail : Pair) (length : W) (s : Pair) : Pair :=
  let v := addPair (s.1 ^^^ tail.1 ^^^ length, s.2 ^^^ tail.2 ^^^ length)
  addPair (avalanche v.1,avalanche v.2)

theorem final_inj (tail : Pair) (length : W) : Injective (finalPair tail length) := by
  intro a b h
  let x := addPair (a.1 ^^^ tail.1 ^^^ length,a.2 ^^^ tail.2 ^^^ length)
  let y := addPair (b.1 ^^^ tail.1 ^^^ length,b.2 ^^^ tail.2 ^^^ length)
  have e : (avalanche x.1,avalanche x.2)=(avalanche y.1,avalanche y.2) := addPair_inj h
  have v : x=y := Prod.ext (avalanche_inj (congrArg Prod.fst e)) (avalanche_inj (congrArg Prod.snd e))
  have z := addPair_inj v
  apply Prod.ext
  · exact (BitVec.xor_left_inj tail.1).mp ((BitVec.xor_left_inj length).mp (congrArg Prod.fst z))
  · exact (BitVec.xor_left_inj tail.2).mp ((BitVec.xor_left_inj length).mp (congrArg Prod.snd z))

theorem blocks_inj (ks : List Pair) : Injective (fun s => ks.foldl step s) := by
  induction ks with
  | nil => exact fun _ _ eq => eq
  | cons k ks ih => exact fun _ _ eq => step_inj k (ih eq)

def output (ks : List Pair) (tail : Pair) (length seed : W) : Pair :=
  finalPair tail length (ks.foldl step (seed,seed))

theorem output_inj (ks : List Pair) (tail : Pair) (length : W) : Injective (output ks tail length) := by
  intro a b h
  exact congrArg Prod.fst (blocks_inj ks (final_inj tail length h))

/-- Blocks and tail words have already been mixed with the fixed input bytes. None depends on the seed. -/
theorem signed_seed_boundary (ks : List Pair) (tail : Pair) (length : W) (seed : BitVec 32) :
    output ks tail length (seed.signExtend 64) = output ks tail length (seed.zeroExtend 64) ↔ seed.msb=false := by
  have boundary : seed.signExtend 64 = seed.zeroExtend 64 ↔ seed.msb=false := by bv_decide
  constructor
  · exact fun h => boundary.mp (output_inj ks tail length h)
  · intro h; rw [boundary.mpr h]

#print axioms step_inj
#print axioms avalanche_inj
#print axioms output_inj
#print axioms signed_seed_boundary
end Seed128
