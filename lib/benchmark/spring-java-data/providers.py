"""Verify which original class bytes the real public operations load on every selected classpath."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
import zipfile

from measure import ROOT, SETUP, digest, read, seed, write
from targets import route, runtime, runtime_jdk, runtime_jar, sidecar

CLASSES = {
    368: ["springwork.BindingHistory", "org.springframework.validation.DataBinder", "org.springframework.beans.BeanWrapperImpl"],
    369: ["datawork.RowMapper", "org.apache.commons.lang3.math.NumberUtils"],
    370: ["springwork.RoleApplication", "org.springframework.security.access.hierarchicalroles.RoleHierarchyImpl",
          "org.springframework.security.authorization.AuthorityAuthorizationManager"],
    371: ["javaslang.collection.List", "javaslang.collection.Collections", "javaslang.collection.Iterator"],
    372: ["springwork.Accessors", "org.springframework.core.convert.Property"],
    373: ["datawork.NanSearch", "org.apache.commons.lang3.ArrayUtils"],
    374: ["org.springframework.format.datetime.DateFormatterRegistrar", "org.springframework.validation.DataBinder"],
    375: ["org.apache.commons.lang3.math.NumberUtils", "org.apache.commons.lang3.StringUtils"]
}

def observe(number, side, folder, plan, out):
    with tempfile.TemporaryDirectory(prefix="public-class-loads-") as tmp:
        work=Path(tmp)
        stage=work/"prepared"
        target=runtime.prepare(plan,side,stage)
        if target.stage!="artifacts-ready":raise ValueError(target.diagnostic)
        driver,=[a for a in target.artifacts if a.role=="driver"]
        paths=[stage/driver.path,*[stage/p for p in target.classpath]]
        jdk=Path(runtime_jdk.home("21"))
        trace=work/"loads.log"
        package="springwork" if number in (368,370,372,374) else "datawork"
        run=subprocess.run([jdk/"bin/java","-Xmx256m","-Duser.language=en","-Duser.country=US","-Duser.timezone=UTC",
                "-Xlog:class+load=info:file="+str(trace)+":none","-cp",os.pathsep.join(map(str,paths)),package+".Cases","--all"],
                capture_output=True,check=True)
        # The traced process must give every same observation as the uninstrumented public workflow.
        recorded=next(p for p in sorted(folder.glob("receipts/replay*/*/records/control-"+side+"-jdk21.stdout")) if p.is_file())
        if run.stdout.splitlines()!=recorded.read_bytes().splitlines():raise ValueError("class logging changed the public result")
        lines=trace.read_text().splitlines()
        selected={}
        for name in CLASSES[number]:
            marker=name+" source: "
            origins={s[len(marker):] for s in lines if s.startswith(marker)}
            if len(origins)!=1:raise ValueError(f"{number}/{side}: {name} loaded from {origins}")
            uri=urlparse(origins.pop())
            if uri.scheme!="file":raise ValueError(f"{name}: no defining JAR")
            jar=Path(unquote(uri.path)).resolve()
            index=paths.index(jar)
            resource=name.replace(".","/")+".class"
            with zipfile.ZipFile(jar) as archive:
                member=runtime_jar.effective_entries(archive,21)[resource]
                body=archive.read(member)
            if runtime_jar.this_class(body)!=resource[:-6]:raise ValueError("different class declaration")
            selected[name]={"jarIndex":index,"jarSha256":digest(jar),"entry":member.filename,"classSha256":hashlib.sha256(body).hexdigest()}
        return {"commit":target.commit,"jdk":runtime_jdk.release(jdk),"orderedJars":[{"path":p.relative_to(stage).as_posix(),"sha256":digest(p)} for p in paths],
                "classes":selected,"ordinaryRows":len(run.stdout.splitlines()),"ordinarySha256":digest(recorded),
                "ordinary":recorded.relative_to(ROOT).as_posix()}

def main(out):
    os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT",str(SETUP/"src"))
    out.mkdir(parents=True,exist_ok=True)
    data={}
    for number in CLASSES:
        folder,=(ROOT/"examples").glob(str(number)+"-*")
        seed(folder);example=read(folder/"example.json");spec=sidecar.load(folder,example)
        observations={}
        for t in spec["tasks"]:
            if t["kind"]!="replay":continue
            plan=route.resolve(folder,example,spec,t["id"])
            for side in plan.revisions:
                if side not in observations:observations[side]=observe(number,side,folder,plan,out)
        data[str(number)]=observations
        write(out/"classes.json",data)
    parser="org.apache.commons.lang3.math.NumberUtils"
    a,b=data["369"]["landed"]["classes"][parser],data["375"]["landed"]["classes"][parser]
    if (a["jarSha256"],a["classSha256"])!=(b["jarSha256"],b["classSha256"]):
        raise ValueError("the two clients selected different NumberUtils bytecode")

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument("--output",type=Path,required=True)
    main(cli.parse_args().output)
