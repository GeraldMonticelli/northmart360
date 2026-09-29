#!/usr/bin/env python3
from pathlib import Path
import re, sys, hashlib, yaml, zipfile, shutil
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, SKOS

OK = Namespace('https://w3id.org/ontouml/knowledge#')
ONTO = Namespace('https://w3id.org/ontouml#')
PROV = Namespace('http://www.w3.org/ns/prov#')

REF_RE = re.compile(r':ref:`(?:([^`<>]+?)\s*<)?([^`<>]+)>?`', re.I)
HEADING_UNDER_RE = re.compile(r'^[=\-~^"`:+*#]{3,}\s*$')
ENUM_RE = re.compile(r'^\s*(\d+)\.\s*$')
CONSTRAINT_START_RE = re.compile(r'^\s*\*\*C(\d+):\*\*\s*(.*)$', re.I)
ANCHOR_RE = re.compile(r'^\s*\.\.\s+_([^:]+):\s*$')
FIGURE_SUB_RE = re.compile(r'^\s*\.\.\s+\|([^|]+)\|\s+image::\s+(.+?)\s*$')
FIGURE_USE_RE = re.compile(r'^\s*\|([^|]+)\|\s*$')
REF_REGISTRY = {}
KNOWN_SECTION_NAMES = {'full name','type','feature','description','justification','constraints','examples','refactoring plans','references','definition','generic pattern'}


def slug(s): return re.sub(r'[^A-Za-z0-9]+','-',str(s).strip()).strip('-').lower() or 'item'
def stable_uri(kind,*parts):
    key='|'.join(str(x) for x in parts); h=hashlib.sha256(key.encode()).hexdigest()[:16]
    return OK[f'{kind}/{slug(str(parts[-1]))}-{h}']
def source_iri(relpath): return URIRef('urn:ontouml:source:'+str(relpath).replace(' ','%20'))
def add_provenance(g,node,relpath):
    src=source_iri(relpath); g.add((node,PROV.wasDerivedFrom,src)); g.add((src,RDF.type,PROV.Entity)); g.add((src,DCTERMS.identifier,Literal(str(relpath))))
def extract_refs(text): return [((m.group(1) or m.group(2)).strip(),m.group(2).strip()) for m in REF_RE.finditer(text)]
def strip_refs(text):
    text=REF_RE.sub(lambda m:(m.group(1) or m.group(2)).strip(),text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'\1',text); text=re.sub(r'\*([^*]+)\*',r'\1',text)
    text=re.sub(r'``([^`]+)``',r'\1',text); text=re.sub(r'`([^`]+)`__?',r'\1',text)
    text=re.sub(r'[ \t]+',' ',text); text=re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()
def resolve_ref(target):
    key=target.strip().lower()
    return REF_REGISTRY.get(key) or REF_REGISTRY.get(slug(target)) or OK[f'reference/{slug(target)}']
def add_refs(g,subject,text,predicate=OK.references):
    seen=set()
    for label,target in extract_refs(text):
        obj=resolve_ref(target)
        if obj in seen: continue
        seen.add(obj); g.add((subject,predicate,obj)); g.add((obj,RDFS.label,Literal(label))); g.add((obj,OK.referenceKey,Literal(target)))
def read_text(p): return p.read_text(encoding='utf-8',errors='replace')
def figure_substitutions(text): return {m.group(1).strip():m.group(2).strip() for m in map(FIGURE_SUB_RE.match,text.splitlines()) if m}
def clean_unit(lines, figure_map=None):
    figure_map=figure_map or {}; out=[]; figures=[]
    for line in lines:
        if ANCHOR_RE.match(line) or FIGURE_SUB_RE.match(line): continue
        fm=FIGURE_USE_RE.match(line)
        if fm:
            label=fm.group(1).strip(); figures.append((label,figure_map.get(label))); continue
        if re.match(r'^\s*\.\.\s+container::',line) or re.match(r'^\s*\.\.\s+(image|figure)::',line) or re.match(r'^\s*:[\w-]+:',line): continue
        out.append(line.rstrip())
    while out and not out[0].strip(): out.pop(0)
    while out and not out[-1].strip(): out.pop()
    return re.sub(r'\n\s*\n\s*\n+', '\n\n', '\n'.join(out)).strip(),figures
def parse_constraint_units(raw):
    lines=raw.splitlines(); figs=figure_substitutions(raw); starts=[]
    for i,line in enumerate(lines):
        m=CONSTRAINT_START_RE.match(line)
        if m: starts.append((i,int(m.group(1)),m.group(2)))
    units=[]
    for pos,(i,n,rest) in enumerate(starts):
        end=starts[pos+1][0] if pos+1<len(starts) else len(lines)
        body,figures=clean_unit([rest]+lines[i+1:end],figs); units.append((f'C{n}',body,figures))
    return units
def rst_sections(text):
    lines=text.splitlines(); sections=[]; i=0
    while i<len(lines)-1:
        title=lines[i].strip()
        if title and HEADING_UNDER_RE.match(lines[i+1].strip()):
            start=i+2; j=start
            while j<len(lines)-1:
                if lines[j].strip() and HEADING_UNDER_RE.match(lines[j+1].strip()): break
                j+=1
            sections.append((title,'\n'.join(lines[start:j]).strip())); i=j
        else:i+=1
    return sections
def field_blocks(text):
    lines=text.splitlines(); fields={}; i=0
    while i<len(lines):
        key=lines[i].strip().lower()
        if key in KNOWN_SECTION_NAMES:
            label=key; i+=1; buf=[]
            while i<len(lines):
                nxt=lines[i].strip().lower()
                if nxt in KNOWN_SECTION_NAMES or lines[i].startswith('**References:**'): break
                buf.append(lines[i]); i+=1
            fields[label]='\n'.join(buf).strip()
        else:i+=1
    return fields
def numbered_blocks(text):
    lines=text.splitlines(); starts=[]
    for i,line in enumerate(lines):
        m=ENUM_RE.match(line)
        if m: starts.append((i,int(m.group(1))))
    out=[]
    for pos,(i,n) in enumerate(starts):
        end=starts[pos+1][0] if pos+1<len(starts) else len(lines); body,_=clean_unit(lines[i+1:end],figure_substitutions(text)); out.append((n,body))
    return out
def add_text_unit(g,node,kind,label,body,relpath):
    g.add((node,RDF.type,kind)); g.add((node,RDFS.label,Literal(label))); g.add((node,OK.sourceText,Literal(body)))
    cleaned=strip_refs(body)
    if cleaned:g.add((node,SKOS.definition,Literal(cleaned)))
    add_refs(g,node,body); add_provenance(g,node,relpath)

def add_rdf_list(g, subject, predicate, values):
    values=list(dict.fromkeys(values))
    if not values: return
    head=BNode(); Collection(g,head,values); g.add((subject,predicate,head))

def refs_in_parentheses(body):
    # Prefer the first parenthesized group containing OntoUML refs; this captures the explicit enumeration in most constraints.
    for m in re.finditer(r'\(([^()]*(?::ref:`)[^()]*)\)', body, re.S):
        vals=[resolve_ref(t) for _,t in extract_refs(m.group(1))]
        vals=[v for v in vals if str(v).startswith(str(ONTO))]
        if vals: return vals
    return []

def semanticize_constraint(g,c,body,applies_to):
    """Conservative semantic extraction. Every derived assertion is marked DerivedFromText."""
    plain=strip_refs(body); low=plain.lower(); refs=[resolve_ref(t) for _,t in extract_refs(body)]
    onto_refs=list(dict.fromkeys(v for v in refs if str(v).startswith(str(ONTO))))
    derived=False
    def put(p,o):
        nonlocal derived; g.add((c,p,o)); derived=True

    # Modality
    if re.search(r'\b(cannot|can not|may not|must not|forbidden)\b',low): put(OK.modality,OK.Forbidden)
    elif re.search(r'\b(must|always|should|required)\b',low): put(OK.modality,OK.Required)

    # Scope/path and structural relation
    if 'direct or indirect' in low or 'directly or indirectly' in low or 'ancestor' in low or 'descendent' in low or 'descendant' in low:
        put(OK.pathScope,OK.DirectOrIndirect)
    elif 'direct subtype' in low or 'direct sub-type' in low or 'direct supertype' in low or 'direct super-type' in low:
        put(OK.pathScope,OK.Direct)
    if re.search(r'\b(ancestor|super-?type|supertype)\b',low): put(OK.relation,OK.Supertype)
    elif re.search(r'\b(descendent|descendant|sub-?type|subtype)\b',low): put(OK.relation,OK.Subtype)

    # Cardinality
    if re.search(r'\bexactly one\b',low): put(OK.cardinality,Literal(1,datatype=XSD.integer))
    if re.search(r'\bat least one\b',low): put(OK.minCardinality,Literal(1,datatype=XSD.integer))
    if re.search(r'greater (?:or|than or) equal to 2|greater than or equal to 2',low): put(OK.minCardinality,Literal(2,datatype=XSD.integer))

    # Constraint families + typed enumerations
    enum=refs_in_parentheses(body)
    if 'identity provider' in low:
        put(OK.constraintType,OK.IdentityProviderConstraint)
        # Required => explicit allowed provider enumeration. Forbidden => forbidden provider enumeration.
        if (c,OK.modality,OK.Required) in g: add_rdf_list(g,c,OK.allowedIdentityProviders,enum); derived |= bool(enum)
        elif (c,OK.modality,OK.Forbidden) in g: add_rdf_list(g,c,OK.forbiddenIdentityProviders,enum); derived |= bool(enum)
    elif 'identity principles' in low or 'inherit identity' in low:
        put(OK.constraintType,OK.IdentityConstraint)
        if enum: add_rdf_list(g,c,OK.forbiddenTypes if (c,OK.modality,OK.Forbidden) in g else OK.allowedTypes,enum); derived=True
    elif 'rigid' in low:
        put(OK.constraintType,OK.RigidityConstraint)
        if enum: add_rdf_list(g,c,OK.forbiddenTypes if (c,OK.modality,OK.Forbidden) in g else OK.allowedTypes,enum); derived=True
    elif 'partition' in low and ('disjoint' in low or 'complete' in low):
        put(OK.constraintType,OK.PartitionConstraint); put(OK.disjoint,Literal(True)); put(OK.complete,Literal(True))
    elif 'abstract' in low:
        put(OK.constraintType,OK.AbstractnessConstraint); put(OK.requiredAbstract,Literal(True))
    elif 'connected' in low and ('relation stereotyped' in low or 'mediation' in low):
        put(OK.constraintType,OK.RelationConnectionConstraint)
        relation_types=[x for x in onto_refs if x != applies_to]
        if relation_types: add_rdf_list(g,c,OK.requiredRelationTypes,relation_types); derived=True
    elif 'cardinalit' in low:
        put(OK.constraintType,OK.CardinalityConstraint)

    # Generic typed enumeration for explicit forbidden/allowed lists when not already captured.
    if enum and not any((c,p,None) in g for p in []):
        if (c,OK.modality,OK.Forbidden) in g and not list(g.objects(c,OK.forbiddenTypes)) and not list(g.objects(c,OK.forbiddenIdentityProviders)):
            add_rdf_list(g,c,OK.forbiddenTypes,enum); derived=True

    g.add((c,OK.semanticStatus,OK.DerivedFromText if derived else OK.SourceOnly))


def process_language_elements(g,roots):
    ec=cc=0
    for root in roots:
        if not root.exists(): continue
        for meta in root.rglob('meta.yml'):
            if '__MACOSX' in meta.parts: continue
            data=yaml.safe_load(read_text(meta)) or {}
            for _,content in data.items():
                if isinstance(content,dict) and content.get('name'):
                    name=str(content['name']); official=ONTO[name[0].lower()+name[1:]]; REF_REGISTRY[name.lower()]=official; REF_REGISTRY[slug(name)]=official
    for root in roots:
        if not root.exists():continue
        for meta in root.rglob('meta.yml'):
            if '__MACOSX' in meta.parts:continue
            data=yaml.safe_load(read_text(meta)) or {}
            for category,content in data.items():
                if not isinstance(content,dict) or not content.get('name'):continue
                name=str(content['name']); node=OK[f'element/{slug(name)}']; official=ONTO[name[0].lower()+name[1:]]; ec+=1
                g.add((node,RDF.type,OK.LanguageElement)); g.add((node,RDFS.label,Literal(name))); g.add((node,OK.category,Literal(category))); g.add((node,OK.describes,official)); add_provenance(g,node,meta.relative_to(root.parent))
                for k,v in content.items():
                    if k=='name' or v is None:continue
                    for val in (v if isinstance(v,list) else [v]):
                        if isinstance(val,(str,int,float,bool)):g.add((node,OK[slug(k)],Literal(val)))
            parent=meta.parent; dp=parent/'definition.rst'
            if dp.exists():
                raw=read_text(dp); rel=dp.relative_to(root.parent); d=stable_uri('definition',rel); add_text_unit(g,d,OK.Definition,f'{name} definition',clean_unit(raw.splitlines(),figure_substitutions(raw))[0],rel); g.add((node,OK.hasDefinition,d))
            cp=parent/'constraints.rst'
            if cp.exists():
                raw=read_text(cp); rel=cp.relative_to(root.parent)
                for code,body,figures in parse_constraint_units(raw):
                    c=OK[f'constraint/{slug(name)}-{code.lower()}']; cc+=1; add_text_unit(g,c,OK.Constraint,f'{name} {code}',body,rel); g.add((c,OK.code,Literal(code))); g.add((c,OK.appliesTo,official)); g.add((node,OK.hasConstraint,c)); semanticize_constraint(g,c,body,official)
                    for label,path in figures:
                        fig=stable_uri('figure',rel,label); g.add((c,OK.hasFigure,fig)); g.add((fig,RDF.type,OK.Figure)); g.add((fig,RDFS.label,Literal(label)))
                        if path:g.add((fig,OK.sourcePath,Literal(path)))
    return ec,cc

def process_theory(g,root):
    n=0
    if not root.exists():return n
    for p in root.rglob('*.rst'):
        if '__MACOSX' in p.parts or p.name=='index.rst':continue
        raw=read_text(p); secs=rst_sections(raw); title=secs[0][0] if secs else p.stem.replace('_',' ').title(); node=OK[f'theory/{slug(p.stem)}']; n+=1; body=clean_unit(raw.splitlines(),figure_substitutions(raw))[0]; add_text_unit(g,node,OK.TheoryConcept,title,body,p.relative_to(root.parent))
    return n

def process_patterns(g,root):
    n=0
    if not root.exists():return n
    for d in sorted(x for x in root.iterdir() if x.is_dir() and x.name!='__MACOSX'):
        idx=d/'index.rst'
        if not idx.exists():continue
        raw=read_text(idx); secs=rst_sections(raw); title=secs[0][0] if secs else d.name; node=OK[f'pattern/{slug(d.name)}']; n+=1; g.add((node,RDF.type,OK.Pattern)); g.add((node,RDFS.label,Literal(title))); add_refs(g,node,raw); add_provenance(g,node,idx.relative_to(root.parent))
        for fname,typ,pred in [('generic.rst',OK.PatternStructure,OK.hasStructure),('examples.rst',OK.Example,OK.hasExample)]:
            p=d/fname
            if p.exists():
                rawp=read_text(p); body=clean_unit(rawp.splitlines(),figure_substitutions(rawp))[0]; sub=stable_uri('pattern-part',p.relative_to(root.parent),fname); add_text_unit(g,sub,typ,f'{title} {fname[:-4]}',body,p.relative_to(root.parent)); g.add((node,pred,sub))
    return n

def process_antipatterns(g,root):
    n=conds=refs=0
    if not root.exists():return n,conds,refs
    for d in sorted(x for x in root.iterdir() if x.is_dir() and x.name!='__MACOSX'):
        p=d/'index.rst'
        if not p.exists():continue
        raw=read_text(p); fields=field_blocks(raw); title=strip_refs(fields.get('full name','')) or d.name; node=OK[f'antipattern/{slug(d.name)}']; n+=1; g.add((node,RDF.type,OK.AntiPattern)); g.add((node,RDFS.label,Literal(title))); g.add((node,OK.code,Literal(d.name))); add_provenance(g,node,p.relative_to(root.parent)); add_refs(g,node,raw)
        for key,pred in [('type',OK.antiPatternType),('feature',OK.feature),('description',SKOS.definition),('justification',OK.justification)]:
            val=fields.get(key,'')
            if val:g.add((node,pred,Literal(strip_refs(val)))); add_refs(g,node,val)
        ctext=fields.get('constraints',''); blocks=numbered_blocks(ctext) or ([(1,clean_unit(ctext.splitlines(),figure_substitutions(ctext))[0])] if ctext.strip() else [])
        for num,body in blocks:
            c=OK[f'antipattern/{slug(d.name)}/condition-{num}']; conds+=1; add_text_unit(g,c,OK.DetectionCondition,f'{d.name} condition {num}',body,p.relative_to(root.parent)); g.add((c,OK.order,Literal(num,datatype=XSD.integer))); g.add((node,OK.hasCondition,c))
        for num,body in numbered_blocks(fields.get('refactoring plans','')):
            r=OK[f'antipattern/{slug(d.name)}/refactoring-{num}']; refs+=1; mt=re.search(r'\*\*([^*]+)\*\*',body); rt=strip_refs(mt.group(1)) if mt else f'{d.name} refactoring {num}'; add_text_unit(g,r,OK.RefactoringPlan,rt,body,p.relative_to(root.parent)); g.add((r,OK.order,Literal(num,datatype=XSD.integer))); g.add((node,OK.hasRefactoring,r))
    return n,conds,refs

def locate(root,name):
    # Accept either root/name/... or root/name/name/... from extracted ZIPs.
    a=root/name
    if (a/name).exists(): return a/name
    return a

def main():
    src=Path(sys.argv[1] if len(sys.argv)>1 else '/mnt/data/ontouml_src_v3'); out=Path(sys.argv[2] if len(sys.argv)>2 else '/mnt/data/ontouml-structured-knowledge-v3.ttl')
    g=Graph(); [g.bind(p,n) for p,n in [('ok',OK),('ontouml',ONTO),('prov',PROV),('dct',DCTERMS),('skos',SKOS)]]
    elements,constraints=process_language_elements(g,[locate(src,'classes'),locate(src,'relationships')]); theories=process_theory(g,locate(src,'theory')); patterns=process_patterns(g,locate(src,'patterns')); antis,conditions,refactorings=process_antipatterns(g,locate(src,'anti-patterns'))
    out.parent.mkdir(parents=True,exist_ok=True); g.serialize(out,format='turtle'); check=Graph(); check.parse(out,format='turtle')
    print(f'Language elements       : {elements}\nConstraints             : {constraints}\nTheory concepts         : {theories}\nPatterns                : {patterns}\nAnti-patterns           : {antis}\nDetection conditions    : {conditions}\nRefactoring plans       : {refactorings}\nRDF triples             : {len(g)}\nParse-back triples      : {len(check)}\nOutput                  : {out}')
if __name__=='__main__': main()
