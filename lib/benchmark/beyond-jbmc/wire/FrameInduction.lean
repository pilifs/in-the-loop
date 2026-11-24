import Std.Tactic.BVDecide

namespace FrameInduction

abbrev Byte := BitVec 8
abbrev Seven := BitVec 7
abbrev Word := BitVec 32

inductive Groups where
  | one (a : Seven)
  | two (a b : Seven)
  | three (a b c : Seven)
  | four (a b c d : Seven)
  | five (a b c d : Seven) (e : BitVec 4)

def groups (v : Word) : Groups :=
  let a := v.extractLsb' 0 7
  let b := v.extractLsb' 7 7
  let c := v.extractLsb' 14 7
  let d := v.extractLsb' 21 7
  if v.extractLsb' 7 25 = 0 then .one a
  else if v.extractLsb' 14 18 = 0 then .two a b
  else if v.extractLsb' 21 11 = 0 then .three a b c
  else if v.extractLsb' 28 4 = 0 then .four a b c d
  else .five a b c d (v.extractLsb' 28 4)

def value : Groups → Word
  | .one a => (0 : BitVec 25) ++ a
  | .two a b => (0 : BitVec 18) ++ (b ++ a)
  | .three a b c => (0 : BitVec 11) ++ (c ++ (b ++ a))
  | .four a b c d => (0 : BitVec 4) ++ (d ++ (c ++ (b ++ a)))
  | .five a b c d e => e ++ (d ++ (c ++ (b ++ a)))

theorem full_word (v : Word) : value (groups v) = v := by
  have low14 : v.extractLsb' 7 7 ++ v.extractLsb' 0 7 = v.extractLsb' 0 14 :=
    BitVec.extractLsb'_append_extractLsb'_eq_extractLsb' (by decide)
  have low21 : v.extractLsb' 14 7 ++ v.extractLsb' 0 14 = v.extractLsb' 0 21 :=
    BitVec.extractLsb'_append_extractLsb'_eq_extractLsb' (by decide)
  have low28 : v.extractLsb' 21 7 ++ v.extractLsb' 0 21 = v.extractLsb' 0 28 :=
    BitVec.extractLsb'_append_extractLsb'_eq_extractLsb' (by decide)
  by_cases a : v.extractLsb' 7 25 = 0
  · simp only [groups,ite_eq_left a,value]
    simpa only [a] using (BitVec.extractLsb'_append_extractLsb' (x:=v) (w:=25) (len:=7))
  by_cases b : v.extractLsb' 14 18 = 0
  · simp only [groups,ite_eq_right a,ite_eq_left b,value,low14]
    simpa only [b] using (BitVec.extractLsb'_append_extractLsb' (x:=v) (w:=18) (len:=14))
  by_cases c : v.extractLsb' 21 11 = 0
  · simp only [groups,ite_eq_right a,ite_eq_right b,ite_eq_left c,value,low14,low21]
    simpa only [c] using (BitVec.extractLsb'_append_extractLsb' (x:=v) (w:=11) (len:=21))
  by_cases d : v.extractLsb' 28 4 = 0
  · simp only [groups,ite_eq_right a,ite_eq_right b,ite_eq_right c,ite_eq_left d,value,low14,low21,low28]
    simpa only [d] using (BitVec.extractLsb'_append_extractLsb' (x:=v) (w:=4) (len:=28))
  · simp only [groups,ite_eq_right a,ite_eq_right b,ite_eq_right c,ite_eq_right d,value,low14,low21,low28]
    exact BitVec.extractLsb'_append_extractLsb' (x:=v) (w:=4) (len:=28)

def cont (v : Seven) : Byte := (1 : BitVec 1) ++ v
def last (v : Seven) : Byte := (0 : BitVec 1) ++ v
def high (v : BitVec 4) : Byte := (0 : BitVec 4) ++ v

theorem flags (v : Seven) : (cont v).msb = true ∧ (last v).msb = false ∧
    (cont v).extractLsb' 0 7 = v ∧ (last v).extractLsb' 0 7 = v := by
  simp [cont, last] <;> bv_decide
theorem highBits (v : BitVec 4) : (high v).extractLsb' 4 4 = 0 ∧ (high v).extractLsb' 0 4 = v := by
  simp [high] <;> bv_decide

def varBytes : Groups → List Byte
  | .one a => [last a]
  | .two a b => [cont a,last b]
  | .three a b c => [cont a,cont b,last c]
  | .four a b c d => [cont a,cont b,cont c,last d]
  | .five a b c d e => [cont a,cont b,cont c,cont d,high e]

def parse5 (a b c d : Seven) : List Byte → Option (Groups × List Byte)
  | e::t => if e.extractLsb' 4 4 = 0 then some (.five a b c d (e.extractLsb' 0 4),t) else none
  | [] => none
def parse4 (a b c : Seven) : List Byte → Option (Groups × List Byte)
  | d::t => if d.msb then parse5 a b c (d.extractLsb' 0 7) t else some (.four a b c (d.extractLsb' 0 7),t)
  | [] => none
def parse3 (a b : Seven) : List Byte → Option (Groups × List Byte)
  | c::t => if c.msb then parse4 a b (c.extractLsb' 0 7) t else some (.three a b (c.extractLsb' 0 7),t)
  | [] => none
def parse2 (a : Seven) : List Byte → Option (Groups × List Byte)
  | b::t => if b.msb then parse3 a (b.extractLsb' 0 7) t else some (.two a (b.extractLsb' 0 7),t)
  | [] => none
def parse : List Byte → Option (Groups × List Byte)
  | a::t => if a.msb then parse2 (a.extractLsb' 0 7) t else some (.one (a.extractLsb' 0 7),t)
  | [] => none

theorem parse_suffix (g : Groups) (t : List Byte) : parse (varBytes g ++ t) = some (g,t) := by
  have hc := fun (v : Seven) => (flags v).1
  have hl := fun (v : Seven) => (flags v).2.1
  have dc := fun (v : Seven) => (flags v).2.2.1
  have dl := fun (v : Seven) => (flags v).2.2.2
  have eh := fun (v : BitVec 4) => (highBits v).1
  have el := fun (v : BitVec 4) => (highBits v).2
  cases g <;> simp [varBytes,parse,parse2,parse3,parse4,parse5,hc,hl,dc,dl,eh,el]

def wordBytes (little : Bool) (v : Word) : List Byte :=
  let a := v.extractLsb' 0 8
  let b := v.extractLsb' 8 8
  let c := v.extractLsb' 16 8
  let d := v.extractLsb' 24 8
  if little then [a,b,c,d] else [d,c,b,a]

def wordRead (little : Bool) : List Byte → Option (Word × List Byte)
  | a::b::c::d::tail => some (if little then d ++ c ++ b ++ a else a ++ b ++ c ++ d,tail)
  | _ => none

def reverseWord (v : Word) : Word :=
  v.extractLsb' 0 8 ++ v.extractLsb' 8 8 ++ v.extractLsb' 16 8 ++ v.extractLsb' 24 8

theorem word_suffix (w r : Bool) (v : Word) (t : List Byte) :
    wordRead r (wordBytes w v ++ t) = some (if w=r then v else reverseWord v,t) := by
  cases w <;> cases r <;> simp [wordBytes,wordRead,reverseWord] <;> bv_decide

structure Entry where
  header : Word
  payload : Word

def change (w r : Bool) (x : Entry) : Entry :=
  ⟨if w=r then x.header else reverseWord x.header,x.payload⟩

def emit (little payloadFirst : Bool) (x : Entry) : List Byte :=
  let h := wordBytes little x.header
  let p := varBytes (groups x.payload)
  if payloadFirst then p ++ h else h ++ p

def readEntry (little payloadFirst : Bool) (input : List Byte) : Option (Entry × List Byte) := do
  if payloadFirst then
    let (g,t) ← parse input
    let (h,s) ← wordRead little t
    return (⟨h,value g⟩,s)
  else
    let (h,t) ← wordRead little input
    let (g,s) ← parse t
    return (⟨h,value g⟩,s)

theorem record_suffix (w r ordering : Bool) (entry : Entry) (tail : List Byte) :
    readEntry r ordering (emit w ordering entry ++ tail) = some (change w r entry,tail) := by
  cases ordering <;> simp [readEntry,emit,change,List.append_assoc,word_suffix,parse_suffix,full_word]

def consume (r ordering : Bool) : Nat → List Byte → Option (List Entry × List Byte)
  | 0, input => some ([],input)
  | n+1, input => do
    let (x,t) ← readEntry r ordering input
    let (xs,s) ← consume r ordering n t
    return (x::xs,s)

theorem entire_sequence (w r ordering : Bool) (xs : List Entry) (tail : List Byte) :
    consume r ordering xs.length (xs.flatMap (emit w ordering) ++ tail) =
      some (xs.map (change w r),tail) := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [consume,List.append_assoc,record_suffix,ih]

theorem record_progress (w ordering : Bool) (e : Entry) :
    5 ≤ (emit w ordering e).length ∧ (emit w ordering e).length ≤ 9 := by
  cases w <;> cases ordering <;> cases h : groups e.payload <;> simp [emit,wordBytes,h,varBytes]

theorem prefix_capacity (w ordering : Bool) (pre rest : List Entry) (pos cap : Nat)
    (fit : pos + ((pre++rest).flatMap (emit w ordering)).length ≤ cap) (valid : cap ≤ 2147483647) :
    pos + (pre.flatMap (emit w ordering)).length ≤ cap ∧
    pos + (pre.flatMap (emit w ordering)).length ≤ 2147483647 := by
  simp only [List.flatMap_append,List.length_append] at fit
  omega

#print axioms full_word
#print axioms parse_suffix
#print axioms word_suffix
#print axioms record_suffix
#print axioms entire_sequence
#print axioms record_progress
#print axioms prefix_capacity
end FrameInduction
