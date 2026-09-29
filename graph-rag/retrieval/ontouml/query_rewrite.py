#!/usr/bin/env python3
"""Local NLLB multilingual query rewriting for an English BM25 corpus."""
import argparse, json, re, unicodedata
from functools import lru_cache

MODEL_NAME="facebook/nllb-200-distilled-600M"
TARGET_LANG="eng_Latn"
EXP={
"depend":["dependent","dependency","dependence"],"depends":["depend","dependent","dependency","dependence"],
"dependent":["depend","dependency","dependence"],"dependency":["depend","dependent","dependence"],
"dependence":["depend","dependent","dependency"],"relation":["relationship"],
"relations":["relation","relationship"],"relationship":["relation"],"relationships":["relation","relationship"],
"rigid":["rigidity"],"rigidity":["rigid"],"antirigid":["anti-rigid","anti-rigidity"],
"mediation":["mediate"],"mediate":["mediation"]}
STOP=set("""a an and are as at be been being but by can could did do does doing for from had has have having he her here hers him his how i if in into is it its may might must no not of on or our ours she should so some such than that the their theirs them then there these they this those to too under up us was we were what when where which while who why will with would you your yours""".split())

def nfkc(s): return unicodedata.normalize("NFKC",s).strip()

@lru_cache(maxsize=1)
def load_model():
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    tok=AutoTokenizer.from_pretrained(MODEL_NAME)
    model=AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    device=torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device); model.eval()
    return tok,model,device

def translate(text,src):
    if src==TARGET_LANG: return text
    import torch
    tok,model,device=load_model()
    tok.src_lang=src
    inputs={k:v.to(device) for k,v in tok(text,return_tensors="pt",truncation=True).items()}
    target_id=tok.convert_tokens_to_ids(TARGET_LANG)
    if target_id is None or target_id==tok.unk_token_id: raise ValueError("Unknown NLLB target code")
    with torch.inference_mode():
        out=model.generate(**inputs,forced_bos_token_id=target_id,max_new_tokens=128,num_beams=4)
    return tok.batch_decode(out,skip_special_tokens=True)[0].strip()

def toks(s):
    s=nfkc(s).lower().replace("_"," ")
    return re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)*\b",s)

def uniq(xs):
    out=[]; seen=set()
    for x in xs:
        if x and x not in seen: seen.add(x); out.append(x)
    return out

def rewrite_query(query,src):
    normalized=nfkc(query); english=translate(normalized,src)
    base=[x for x in toks(english) if x not in STOP]; terms=list(base); expansions=[]
    for x in base:
        e=EXP.get(x,[])
        if e: terms+=e; expansions.append({"source":x,"target":e})
    terms=uniq(terms)
    return {"original_query":query,"normalized_query":normalized,"source_language":src,
      "target_language":TARGET_LANG,"english_translation":english,"lexical_terms":terms,
      "bm25_query":" ".join(terms),"expansions":expansions,
      "model":MODEL_NAME if src!=TARGET_LANG else None,
      "policy":{"runtime":"local","uses_llm":False,"uses_external_translation_api":False,"ontology_inference":False}}

def main():
    p=argparse.ArgumentParser(); p.add_argument("query"); p.add_argument("--src",required=True,
      help="NLLB code: fra_Latn, nld_Latn, deu_Latn, eng_Latn, ..."); p.add_argument("--json",action="store_true")
    a=p.parse_args(); r=rewrite_query(a.query,a.src)
    if a.json: print(json.dumps(r,indent=2,ensure_ascii=False)); return
    print("Original     :",r["original_query"]); print("NFKC         :",r["normalized_query"])
    print("Source       :",r["source_language"]); print("English      :",r["english_translation"])
    print("Lexical terms:",r["lexical_terms"]); print("BM25 query   :",r["bm25_query"])
if __name__=="__main__": main()
