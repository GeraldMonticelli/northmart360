from pathlib import Path
from lxml import etree
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, Literal, BNode
from rdflib.namespace import SH
import re

BASE=Path('/mnt/data/oscal_src/src/metaschema')
ROOT=BASE/'oscal_complete_metaschema.xml'
OSCAL=Namespace('https://csrc.nist.gov/ns/oscal/semantic/1.0#')
MS='http://csrc.nist.gov/ns/oscal/metaschema/1.0'
NS={'m':MS}

def camel(s):
    return ''.join(x[:1].upper()+x[1:] for x in re.split(r'[-_]+',s) if x)
def iri_name(s):
    return re.sub(r'[^A-Za-z0-9_.-]','_',s)
def text(el, path):
    x=el.find(path,NS)
    if x is None:return None
    t=' '.join(''.join(x.itertext()).split())
    return t or None

def parse(p):
    parser=etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=True, recover=False)
    return etree.parse(str(p),parser).getroot()

def collect(p, seen=None):
    seen=seen or set(); p=p.resolve()
    if p in seen:return []
    seen.add(p); r=parse(p); out=[(p,r)]
    for imp in r.findall('m:import',NS):
        q=(p.parent/imp.get('href')).resolve()
        if q.exists(): out += collect(q,seen)
    return out

mods=collect(ROOT)
assemblies={}; fields={}
for p,r in mods:
    for e in r.findall('m:define-assembly',NS): assemblies.setdefault(e.get('name'),e)
    for e in r.findall('m:define-field',NS): fields.setdefault(e.get('name'),e)

DT={
 'string':XSD.string,'token':XSD.token,'boolean':XSD.boolean,'integer':XSD.integer,
 'non-negative-integer':XSD.nonNegativeInteger,'positive-integer':XSD.positiveInteger,
 'decimal':XSD.decimal,'date':XSD.date,'date-time':XSD.dateTime,'date-time-with-timezone':XSD.dateTime,
 'uri':XSD.anyURI,'uri-reference':XSD.anyURI,'uuid':XSD.string,'base64':XSD.base64Binary,
 'email-address':XSD.string,'hostname':XSD.string,'ip-v4-address':XSD.string,'ip-v6-address':XSD.string,
 'markup-line':RDF.HTML,'markup-multiline':RDF.HTML
}
def dtype(t): return DT.get(t or 'string',XSD.string)

g=Graph(); s=Graph()
for G in (g,s):
    G.bind('oscal',OSCAL); G.bind('rdf',RDF); G.bind('rdfs',RDFS); G.bind('owl',OWL); G.bind('xsd',XSD); G.bind('sh',SH)
g.add((OSCAL.Ontology,RDF.type,OWL.Ontology)); g.add((OSCAL.Ontology,RDFS.label,Literal('OSCAL semantic projection generated from NIST Metaschema')))

# classes
for name,e in sorted(assemblies.items()):
    C=OSCAL[camel(name)]; g.add((C,RDF.type,OWL.Class))
    g.add((C,RDFS.label,Literal(text(e,'m:formal-name') or name)))
    if d:=text(e,'m:description'): g.add((C,RDFS.comment,Literal(d)))

# reusable property registry
prop_kinds={}
def add_prop(pname, kind, domain=None, range_=None, label=None, comment=None):
    P=OSCAL[iri_name(pname)]
    typ=OWL.ObjectProperty if kind=='object' else OWL.DatatypeProperty
    if (P,RDF.type,typ) not in g:g.add((P,RDF.type,typ))
    if domain:g.add((P,RDFS.domain,domain))
    if range_:g.add((P,RDFS.range,range_))
    if label:g.add((P,RDFS.label,Literal(label)))
    if comment:g.add((P,RDFS.comment,Literal(comment)))
    return P

def card(ref):
    mn=ref.get('min-occurs')
    mx=ref.get('max-occurs')
    if ref.tag.endswith('flag') and ref.get('required')=='yes': mn='1'
    if ref.tag.endswith('flag'): mx='1'
    return mn,mx

def enum_values(defel):
    vals=[]
    for av in defel.findall('.//m:allowed-values',NS):
        for en in av.findall('m:enum',NS):
            if en.get('value') is not None: vals.append(en.get('value'))
    return list(dict.fromkeys(vals))

def add_shape_prop(shape,P,mn,mx,dt=None,cls=None,enums=None):
    b=BNode(); s.add((shape,SH.property,b)); s.add((b,SH.path,P))
    if mn is not None:
        try:s.add((b,SH.minCount,Literal(int(mn))))
        except:pass
    if mx not in (None,'unbounded'):
        try:s.add((b,SH.maxCount,Literal(int(mx))))
        except:pass
    if cls:s.add((b,SH['class'],cls))
    elif dt:s.add((b,SH.datatype,dt))
    if enums:
        head=BNode(); cur=head
        for i,v in enumerate(enums):
            s.add((cur,RDF.first,Literal(v)))
            nxt=RDF.nil if i==len(enums)-1 else BNode(); s.add((cur,RDF.rest,nxt)); cur=nxt
        s.add((b,SH['in'],head))

for aname,a in sorted(assemblies.items()):
    C=OSCAL[camel(aname)]; shape=OSCAL[camel(aname)+'Shape']
    s.add((shape,RDF.type,SH.NodeShape)); s.add((shape,SH.targetClass,C)); s.add((shape,RDFS.label,Literal((text(a,'m:formal-name') or aname)+' shape')))
    # inline + referenced flags
    for f in list(a.findall('m:define-flag',NS))+list(a.findall('m:flag',NS)):
        ref=f.get('ref'); de=f if f.tag.endswith('define-flag') else None
        if ref and de is None:
            # flags are usually local to a definition; unresolved refs default string
            fname=f.get('use-name') or ref; typ='string'; label=fname; desc=None; enums=[]
        else:
            fname=f.get('name'); typ=f.get('as-type') or 'string'; label=text(f,'m:formal-name') or fname; desc=text(f,'m:description'); enums=enum_values(f)
        P=add_prop(fname,'data',C,dtype(typ),label,desc); mn,mx=card(f); add_shape_prop(shape,P,mn,mx,dt=dtype(typ),enums=enums)
    model=a.find('m:model',NS)
    if model is None: continue
    for x in model:
        if not isinstance(x.tag, str): continue
        tag=etree.QName(x).localname
        if tag=='assembly':
            ref=x.get('ref'); pname=x.get('use-name') or ref
            if ref in assemblies:
                target=OSCAL[camel(ref)]; P=add_prop(pname,'object',C,target,pname); mn,mx=card(x); add_shape_prop(shape,P,mn,mx,cls=target)
        elif tag=='field':
            ref=x.get('ref'); pname=x.get('use-name') or ref
            de=fields.get(ref); typ=(de.get('as-type') if de is not None else None) or 'string'
            label=(text(de,'m:formal-name') if de is not None else None) or pname
            desc=text(de,'m:description') if de is not None else None
            enums=enum_values(de) if de is not None else []
            P=add_prop(pname,'data',C,dtype(typ),label,desc); mn,mx=card(x); add_shape_prop(shape,P,mn,mx,dt=dtype(typ),enums=enums)
        # choices are intentionally left for v2; nested refs inside choice still get picked below
    # refs nested in choice/group not direct model children
    for x in model.xpath('.//m:assembly | .//m:field',namespaces=NS):
        # skip direct children already processed
        if x.getparent() is model: continue
        tag=etree.QName(x).localname; ref=x.get('ref'); pname=x.get('use-name') or ref
        if tag=='assembly' and ref in assemblies:
            target=OSCAL[camel(ref)]; P=add_prop(pname,'object',C,target,pname); mn,mx=card(x); add_shape_prop(shape,P,mn,mx,cls=target)
        elif tag=='field':
            de=fields.get(ref); typ=(de.get('as-type') if de is not None else None) or 'string'; enums=enum_values(de) if de is not None else []
            P=add_prop(pname,'data',C,dtype(typ),pname); mn,mx=card(x); add_shape_prop(shape,P,mn,mx,dt=dtype(typ),enums=enums)

out1=Path('/mnt/data/oscal-ontology.ttl'); out2=Path('/mnt/data/oscal-shapes.ttl')
g.serialize(out1,format='turtle'); s.serialize(out2,format='turtle')
print('modules',len(mods),'assemblies',len(assemblies),'fields',len(fields),'ontology triples',len(g),'shape triples',len(s))
# validate syntax
Graph().parse(out1,format='turtle'); Graph().parse(out2,format='turtle')
print(out1, out2)
