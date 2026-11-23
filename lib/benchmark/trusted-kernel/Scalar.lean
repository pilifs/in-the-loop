import Lean

/- Read the complete class from the consumer's working directory. The term given to
   the kernel is just a literal list; neither javap nor a producer supplies offsets. -/
elab "artifactBytes" : term => do
  let bytes ← IO.FS.readBinFile "artifact.bin"
  return Lean.toExpr (bytes.data.toList.map UInt8.toNat)

namespace ScalarKernel

abbrev Bytes := List Nat
abbrev Read := StateT Bytes Option
def takeN (n : Nat) : Read Bytes := fun s =>
  if n ≤ s.length then some (s.take n, s.drop n) else none
def u1 : Read Nat := fun s => match s with
  | x :: xs => some (x,xs)
  | [] => none
def u2 : Read Nat := do return (← u1)*256 + (← u1)
def u4 : Read Nat := do return (← u2)*65536 + (← u2)

inductive CP where
  | unused
  | utf (s : String)
  | cls (name : Nat)
  deriving Inhabited
def readMany {α : Type} (item : Read α) : Nat → Read (List α)
  | 0 => pure []
  | n+1 => do let x ← item; return x :: (← readMany item n)

def cpEntry : Read CP := do
  match ← u1 with
  | 1 => return .utf (String.ofList ((← takeN (← u2)).map Char.ofNat))
  | 7 => return .cls (← u2)
  | 10 | 12 => let _ ← takeN 4; return .unused
  | _ => failure

def poolString (cp : List CP) (idx : Nat) : Option String := do
  let .utf s ← cp[idx]? | none
  return s
def poolClass (cp : List CP) (idx : Nat) : Option String := do
  let .cls n ← cp[idx]? | none
  poolString cp n

structure Method where
  flags : Nat
  name : String
  descriptor : String
  code : Bytes
  deriving DecidableEq

def method (cp : List CP) : Read Method := do
  let flags ← u2
  let some name := poolString cp (← u2) | failure
  let some desc := poolString cp (← u2) | failure
  guard ((← u2) == 1)
  guard (poolString cp (← u2) == some "Code")
  let body ← takeN (← u4)
  let reader : Read Bytes := do
    let _ ← u2
    let locals ← u2
    guard (locals ≥ 1)
    let bytes ← takeN (← u4)
    guard ((← u2) == 0 && (← u2) == 0)
    return bytes
  let some (bytes, []) := reader.run body | failure
  return ⟨flags,name,desc,bytes⟩

def classFile : Read (String × List Method) := do
  guard ((← u4) == 0xcafebabe)
  guard ((← u2) == 0 && (← u2) == 65)
  let n ← u2
  guard (n > 0)
  let cp := CP.unused :: (← readMany cpEntry (n-1))
  guard ((← u2) == 0x31)
  let some owner := poolClass cp (← u2) | failure
  guard (poolClass cp (← u2) == some "java/lang/Object")
  guard ((← u2) == 0 && (← u2) == 0)
  let ms ← readMany (method cp) (← u2)
  guard ((← u2) == 0)
  return (owner,ms)

def codeFor (bytes : Bytes) (owner name desc : String) : Option Bytes := do
  let ((actual,ms), []) ← classFile.run bytes | none
  guard (actual == owner)
  let [m] := ms.filter (fun m => m.name == name && m.descriptor == desc) | none
  guard (m.flags == 9)
  return m.code

abbrev Word := BitVec 32
/- The supported instructions only affect the integer operand stack. Returning the
   incoming heap in 'call' expresses their frame for every possible heap. -/
def execute (x : Word) : Bytes → List Word → Option Word
  | 0x1a :: bs, s => execute x bs (x::s)
  | 0x04 :: bs, s => execute x bs (1::s)
  | 0x05 :: bs, s => execute x bs (2::s)
  | 0x60 :: bs, a::b::s => execute x bs ((b+a)::s)
  | 0x68 :: bs, a::b::s => execute x bs ((b*a)::s)
  | [0xac], [v] => some v
  | _, _ => none

def bytes : Bytes := artifactBytes
def call {Heap : Type} (name : String) (x : Word) (h : Heap) : Option (Word × Heap) := do
  let code ← codeFor bytes "fixtures/Scalar" name "(I)I"
  return (← execute x code [], h)

set_option maxRecDepth 8192
set_option maxHeartbeats 4000000
theorem multiplyCode : codeFor bytes "fixtures/Scalar" "multiply" "(I)I" = some [5,26,104,172] := by decide
theorem addCode : codeFor bytes "fixtures/Scalar" "add" "(I)I" = some [26,26,96,172] := by decide
theorem shiftedCode : codeFor bytes "fixtures/Scalar" "shifted" "(I)I" = some [26,26,96,4,96,172] := by decide

theorem originalBytesEqual {Heap : Type} (x : Word) (h : Heap) :
    call "multiply" x h = some (x+x,h) ∧ call "add" x h = some (x+x,h) := by
  simp only [call, multiplyCode, addCode]
  change some (2#32*x,h) = some (x+x,h) ∧ some (x+x,h) = some (x+x,h)
  rw [BitVec.two_mul]
  exact ⟨rfl,rfl⟩

theorem shiftedRefuted : call "multiply" 0 () ≠ call "shifted" 0 () := by
  simp only [call, multiplyCode, shiftedCode]
  decide

#print axioms originalBytesEqual
#print axioms shiftedRefuted
end ScalarKernel
