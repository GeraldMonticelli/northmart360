#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
DEFAULT_SOURCE=(HERE/"../ontouml/ontouml-language").resolve()
CORPUS=HERE/"corpus"/"ontouml-language"
MANIFEST=HERE/"manifest.json"
ROOTS=("theory","classes","relationships","patterns","anti-patterns")

def git_commit(repo):
    try: return subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,default=DEFAULT_SOURCE)
    source=ap.parse_args().source.resolve()
    if not source.is_dir(): raise SystemExit(f"Source not found: {source}")
    if CORPUS.exists(): shutil.rmtree(CORPUS)
    CORPUS.mkdir(parents=True)
    docs=[]; counts={x:0 for x in ROOTS}
    for domain in ROOTS:
        root=source/domain
        if not root.exists():
            print(f"WARNING missing: {root}"); continue
        for src in sorted(root.rglob("*.rst")):
            rel=src.relative_to(source); dst=CORPUS/rel
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
            docs.append({"path":rel.as_posix(),"sha256":digest(src),"bytes":src.stat().st_size})
            counts[domain]+=1
    old=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    old.update({"schema_version":1,
      "source":{"repository":"ontouml-language","path":str(source),"git_commit":git_commit(source)},
      "corpus":{"built_at_utc":datetime.now(timezone.utc).isoformat(),
                "included_roots":list(ROOTS),"document_count":len(docs),
                "counts_by_domain":counts,"documents":docs}})
    MANIFEST.write_text(json.dumps(old,indent=2,ensure_ascii=False)+"\n")
    print(f"Corpus: {CORPUS}\nDocuments: {len(docs)}")
    for k,v in counts.items(): print(f"  {k:16} {v}")

if __name__=="__main__": main()
