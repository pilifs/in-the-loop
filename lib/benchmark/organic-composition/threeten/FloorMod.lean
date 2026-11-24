import Std
namespace ThreeTen

/-- JVM lrem truncates toward zero. The first addition fits in a Java long
    and the final remainder fits in a Java int, for every signed epoch. -/
theorem floorMod86400 (a : Int) :
    let r := a.tmod 86400
    0 < r + 86400 ∧ r + 86400 < 172800 ∧
    (r + 86400).tmod 86400 = a % 86400 ∧
    0 ≤ a % 86400 ∧ a % 86400 < 86400 := by
  dsimp
  have hr : -86400 < a.tmod 86400 ∧ a.tmod 86400 < 86400 := by
    rw [Int.tmod_eq_emod]
    split <;> omega
  have he := Int.tmod_add_mul_tdiv a 86400
  rw [Int.tmod_eq_emod_of_nonneg (by omega : 0 ≤ a.tmod 86400 + 86400)]
  omega

#print axioms floorMod86400
end ThreeTen
