"""Public control inputs for the disclosed arithmetic, reference topology and receiver histories."""
from subjects import Claim, Subject

CASES = {}
COMPILE = {}
JOINT = {"guava-lang": ("guava-33.4.8-jre","commons-lang3-3.17.0")}
LANG = "commons-lang3-3.17.0"
def put(key, owner, graph, claims, *, bound=8, unwind=16, compile_on=None):
    CASES[key]=("extended",Subject(0,owner,graph,tuple(claims),bound,unwind))
    if compile_on:COMPILE[owner,graph]=compile_on
def one(*values):return tuple((str(v),) for v in values)
def truth(method,parameters="",seeds=((),),negative=()):
    return Claim(method,parameters,holds=seeds,fails=negative)

put("N03","Cancellation","vecmath-1.5.2",[
    truth("rounds","int n",one(1,1448,1449,2048)),truth("fused","int n",one(2048),one(1,1448))])
chars=one("'0'","'f'","' '","(char)0x661","(char)0xd800")
put("N06","Lexical",LANG,[truth(m,"char c",chars) for m in ("commons","partition")])
cpairs=(("'K'","(char)0x212a"),("'A'","'a'"),("(char)0xd800","(char)0xd801"))
put("N07","CaseFolding","guava-lang",[truth(m,"char a, char b",cpairs) for m in ("strings","sequences")]+[
    truth("same","char a, char b",cpairs[1:],cpairs[:1]),truth("nulls")])
nan=(("0x7ff8000000000001L","0xfff8000000000000L"),("0x7ff0000000000001L","0x7ff8000000000001L"))
for v in ("1.1","1.2"):
    wanted=v=="1.2"
    put("N08-"+v,"BoxedFP","commons-numbers-"+v,[
        truth("zeroEquals"),truth("zeroHashes",seeds=((),) if wanted else (),negative=() if wanted else ((),)),
        truth("nanEquality","long x, long y",nan if wanted else (("0L","0L"),),() if wanted else nan),
        truth("nanOrder","long x, long y",nan)],compile_on="commons-numbers-1.1")
for v in ("1.18.2","1.20.0"):
    put("N09-"+v,"OrientationGrid","jts-core-"+v,[
        truth("box","int x, int y, int u, int v",(("1","0","0","1"),("2","2","-7","-7"),("-8","7","7","-8"))),
        truth("cancellation","int n",one(1,100000000,1073741822))],compile_on="jts-core-1.18.2")

put("H01","HeapTopology",LANG,[
    truth("entry","HeapTopology.Cell[] cells",one("new HeapTopology.Cell[]{HeapTopology.cell(new org.apache.commons.lang3.mutable.MutableInt(-1))}")),
    truth("constructed","int value, int mode",(("0","0"),("Integer.MAX_VALUE","1"),("-1","2"))),
    truth("unchanged","int value",(),one(-1,"Integer.MAX_VALUE"))])
put("H02","HeapTopology",LANG,[truth("walk","int topology, int start",(("0","-1"),("1","0"),("6","0"),("63","2")))])
put("H03","HeapTopology",LANG,[truth("twoRoots","int value, boolean shared",(("Integer.MAX_VALUE","true"),("7","false"),("7","true")))])
for v in ("3.1.4","4.0.2"):
    put("H04-"+v,"PersistentVector","pcollections-"+v,[
        truth("branches","int n, int i, int replacement",(("1","0","-1"),("6","3","12"),("6","0","0")))],compile_on="pcollections-3.1.4")
for v in ("1.6.15","1.6.16","1.6.17","1.6.18"):
    old=v in ("1.6.15","1.6.16")
    put("H05-H06-"+v,"IteratorHistories","RoaringBitmap-"+v,[
        truth("forward","int steps",one(0,1,2) if old else one(0,1,3,6),one(3,6) if old else ()),
        truth("reverse","int alternate",() if old else one(0,1),one(0,1) if old else ())],compile_on="RoaringBitmap-1.6.15")
for v in ("1.6.25","1.6.26","1.6.27","1.6.28"):
    old=v in ("1.6.25","1.6.26")
    put("H07-"+v,"IteratorHistories","RoaringBitmap-"+v,[
        truth("subset","int hole, int d",(("64","0"),("4096","2"))+(() if old else (("64","1"),)),(("64","1"),) if old else ()),
        truth("interval","int hole, int d",(("64","0"),("64","1"),("4096","2")))],compile_on="RoaringBitmap-1.6.25")
for v in ("1.18.1","1.18.2"):
    old=v=="1.18.1"
    put("H08-"+v,"MarkupHistory","jsoup-"+v,[
        truth("form","boolean html",one("true") if old else one("true","false"),one("false") if old else ()),
        truth("reparent",seeds=() if old else ((),),negative=((),) if old else ())],compile_on="jsoup-1.18.1")
for v in ("1.18.2","1.18.3"):
    old=v=="1.18.2"
    put("H09-"+v,"MarkupHistory","jsoup-"+v,[
        truth("xml","char interior",one("'a'","'_'") if old else one("'a'","'_'","'-'","'.'","'1'"),one("'-'","'.'","'1'") if old else ())],compile_on="jsoup-1.18.2")
put("H10","HeapTopology",LANG,[truth("planes","boolean shared, char x, char y",(("true","'z'","'z'"),("false","'a'","'b'")))])
initial=(("Integer.MAX_VALUE","true"),("7","true"),("7","false"))
put("H11","RootShapes","jdk",[
    truth("arrayRoots","int x, int y, boolean shared",(("7","7","false"),("2","3","true"))),
    truth("unconditional","boolean shared",one("false"),one("true"))])
put("H12","RootShapes","jdk",[truth("scalarRoot","int initial, boolean shared",initial)])
put("H13","RootShapes","jdk",[truth("mapping","int choice",one(0,1,2)),truth("alwaysFour","int choice",one(0),one(1,2))])
put("H14","RootShapes","jdk",[truth("linked","int shape",one(0,1,2)),truth("noSelf","int shape",one(0,2),one(1))])
for v in ("6.1.3","6.1.14","6.2.0","6.2.3"):
    graph="spring-"+v
    put("S04-S06-"+v,"SpringHistories",graph,[truth(n) for n in ("bridge","aliases","conversion")],compile_on="spring-6.1.3")
    if v in ("6.1.14","6.2.0"):
        put("S07-"+v,"SpringHistories",graph,[truth("listener","boolean list",one("true","false"))],compile_on="spring-6.1.3")
        old=v=="6.1.14"
        put("S08-"+v,"OptionalAssembler",graph,[truth("intended","int order",one(0,1,2,3)),
            truth("otherAbsent","int order",() if old else one(0,1,2,3),one(0,1,2,3) if old else ())],compile_on="spring-6.1.14")
slices=(("new byte[0]","0","0","-1"),("new byte[]{1,-1,2}","1","1","0"),("new byte[]{-1,2,3,4}","0","4","7"))
put("C02","Incremental","commons-codec-1.15",[truth("tail","byte[] a, int off, int len, int seed",slices)])
put("C03-C04","Incremental","commons-codec-1.15",[
    truth("chunks","byte[] a, int off, int len, int split, int seed",(("new byte[0]","0","0","0","0"),("new byte[]{1,2,3,-1,2}","0","5","3","-8"))),
    truth("resetThree","byte[] a, int first, int second, int seed",(("new byte[0]","0","0","0"),("new byte[]{1,-1,2,3,4}","2","4","7")))])
for v in ("5.6.0","5.7.0"):
    padded=(("1","8","0","2","2"),("1","2","3","3","7"))
    normal=(("1","8","0","2","0"),("0","0","0","1","0"))
    old=v=="5.6.0"
    put("C08-"+v,"Coercion","semver4j-"+v,[
        truth("newGrammar","int major, int minor, int patch, int parts, int mask",normal if old else normal+padded,padded if old else ()),
        truth("oldGrammar","int major, int minor, int patch, int parts, int mask",normal+padded if old else normal,() if old else padded), truth("plain")],compile_on="semver4j-5.6.0")
for v in ("6.0.0","6.1.0"):
    old=v=="6.0.0"
    short=one('"0"','"1"','"9"','"9223372036854775807"');big=one('"9223372036854775808"','"10000000000000000000"')
    put("C09-"+v,"VersionOrder","semver4j-"+v,[
        truth("pre","String digits",short if old else short+big,big if old else ()),
        truth("overflow","String digits",short+big if old else short,() if old else big)],bound=24,unwind=32,compile_on="semver4j-6.0.0")
    allpairs=tuple((str(r),str(i)) for r in range(4) for i in range(4))
    bad=(("0","3"),("1","3"),("2","0"),("2","1"),("3","0"),("3","1"))
    put("C10-"+v,"VersionOrder","semver4j-"+v,[truth("caret","int range, int v",
        tuple(t for t in allpairs if t not in bad) if old else allpairs,bad if old else ())],compile_on="semver4j-6.0.0")
put("E01-E03","ThrowSites","jdk",[truth("coarse","int mode",one(0,1,2)),
    truth("history","int mode, boolean replace",tuple((str(m),flag) for m in (0,1,2) for flag in ("true","false")))])
for v in ("6.1.14","6.2.0"):
    put("S03-"+v,"FormatterBinding","spring-"+v,[truth("registeredEnum"),
        truth("annotated","int mode",one(0,1)),truth("preservation","int mode",one(0,1))],compile_on="spring-6.1.14")
put("H02-false","SelfOnly",LANG,[truth("terminates","int topology, int start",(("0","0"),("1","0")),(("6","0"),))])
flat="new SuppliedRoots.Flat()"
distinct=("new SuppliedRoots.Flat[]{"+flat+", "+flat+"}","new SuppliedRoots.Flat[]{"+flat+"}")
put("H10-H14-supplied","SuppliedRoots",LANG,[
    truth("planes","char[][][] data",one("new char[][][]{{{'a'}},{{'b'}}}","new char[2][][]")),
    truth("conditional","SuppliedRoots.Flat[] a, SuppliedRoots.Flat[] b",(distinct,)),
    truth("unconditional","SuppliedRoots.Flat[] a, SuppliedRoots.Flat[] b",(distinct,)),
    truth("scalar","SuppliedRoots.Flat[] a, SuppliedRoots.Flat b",(("new SuppliedRoots.Flat[]{"+flat+"}",flat),)),
    truth("dispatch","SuppliedRoots.Base[] a",one("new SuppliedRoots.Base[]{new SuppliedRoots.Base()}","new SuppliedRoots.Base[]{new SuppliedRoots.Nine()}","new SuppliedRoots.Base[]{new SuppliedRoots.Seven()}")),
    truth("noSelf","SuppliedRoots.Node[] a",one("new SuppliedRoots.Node[]{new SuppliedRoots.Node()}"),one("SuppliedRoots.self()"))],bound=3)
put("N07-individual","FoldProfiles","guava-lang",[truth(m,"char a, char b",cpairs) for m in
    ("guavaString","guavaSequence","langString","langSequence")])
