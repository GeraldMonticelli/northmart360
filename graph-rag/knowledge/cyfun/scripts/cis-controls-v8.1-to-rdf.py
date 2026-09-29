import re
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS

TXT=Path('/mnt/data/cis.txt')
OUT=Path('/mnt/data/cis-controls-v8.1.ttl')
text=TXT.read_text(encoding='utf-8', errors='replace')

CIS=Namespace('https://example.org/cis-controls-v8.1/')  # MUST match CyFun crosswalk
CISO=Namespace('https://example.org/cis-controls-v8.1/ontology#')

control_titles={
1:'Inventory and Control of Enterprise Assets',2:'Inventory and Control of Software Assets',3:'Data Protection',
4:'Secure Configuration of Enterprise Assets and Software',5:'Account Management',6:'Access Control Management',
7:'Continuous Vulnerability Management',8:'Audit Log Management',9:'Email and Web Browser Protections',
10:'Malware Defenses',11:'Data Recovery',12:'Network Infrastructure Management',13:'Network Monitoring and Defense',
14:'Security Awareness and Skills Training',15:'Service Provider Management',16:'Application Software Security',
17:'Incident Response Management',18:'Penetration Testing'}

g=Graph(); g.bind('cis',CIS); g.bind('ciso',CISO); g.bind('dcterms',DCTERMS); g.bind('rdfs',RDFS)
# ontology terms
for cls,label in [('Framework','CIS Controls Framework'),('Control','CIS Control'),('Safeguard','CIS Safeguard'),('AssetType','Asset Type'),('SecurityFunction','Security Function'),('ImplementationGroup','Implementation Group')]:
    g.add((CISO[cls], RDF.type, OWL.Class)); g.add((CISO[cls], RDFS.label, Literal(label)))
for prop,label in [('identifier','identifier'),('belongsToControl','belongs to control'),('assetType','asset type'),('securityFunction','security function'),('implementationGroup','implementation group'),('description','description')]:
    g.add((CISO[prop], RDF.type, OWL.ObjectProperty if prop in {'belongsToControl','assetType','securityFunction','implementationGroup'} else OWL.DatatypeProperty)); g.add((CISO[prop], RDFS.label, Literal(label)))

fw=CIS['framework']; g.add((fw,RDF.type,CISO.Framework)); g.add((fw,RDFS.label,Literal('CIS Critical Security Controls v8.1.2'))); g.add((fw,DCTERMS.issued,Literal('2025-03',datatype=XSD.gYearMonth))); g.add((fw,DCTERMS.source,URIRef('https://www.cisecurity.org/controls/v8-1')))
g.add((fw,DCTERMS.license,URIRef('https://creativecommons.org/licenses/by-nc-nd/4.0/')))

for n,title in control_titles.items():
    u=CIS[str(n)]; g.add((u,RDF.type,CISO.Control)); g.add((u,CISO.identifier,Literal(str(n)))); g.add((u,RDFS.label,Literal(title))); g.add((u,DCTERMS.isPartOf,fw))

# first occurrence of each safeguard is the normative body; later occurrences are index duplicates
allm=list(re.finditer(r'(?m)^\f?Safeguard\s+(\d+\.\d+):[ \t]*(.*)$',text))
seen=set(); parsed=[]
for i,m in enumerate(allm):
    sid=m.group(1)
    if sid in seen: continue
    seen.add(sid)
    title=m.group(2).strip()
    if not title:
        tail=text[m.end():].splitlines()
        title=next((x.strip() for x in tail if x.strip()), '')
    end=allm[i+1].start() if i+1<len(allm) else len(text)
    chunk=text[m.end():end]
    meta=re.search(r'Asset Type:\s*(.*?)\s*\|\s*Security Function:\s*(.*?)\s*\|\s*\|\s*([^\n]+)',chunk)
    if not meta:
        raise RuntimeError(f'Metadata not found for Safeguard {sid}')
    asset=meta.group(1).strip(); function=meta.group(2).strip(); igs=re.findall(r'IG[123]',meta.group(3))
    desc=chunk[meta.end():]
    # remove page headers/footers and cross-page artifacts, preserve source prose otherwise
    lines=[]
    for line in desc.splitlines():
        s=line.strip()
        if not s: lines.append(''); continue
        if re.match(r'^\d+\s+Control\s+\d+:',s): continue
        if re.match(r'^CIS Controls v8\.1\.2\s+',s): continue
        if s.startswith('CONTROL '): break
        if s=='Safeguards': continue
        lines.append(s)
    desc=' '.join(' '.join(lines).split())
    # if next heading belongs to a different control, desc is already bounded by it
    u=CIS[sid]; cn=int(sid.split('.')[0]); cu=CIS[str(cn)]
    g.add((u,RDF.type,CISO.Safeguard)); g.add((u,CISO.identifier,Literal(sid))); g.add((u,RDFS.label,Literal(title))); g.add((u,CISO.belongsToControl,cu)); g.add((u,DCTERMS.isPartOf,fw))
    if desc: g.add((u,CISO.description,Literal(desc)))
    au=CIS['asset-type-'+re.sub(r'[^A-Za-z0-9]+','-',asset).strip('-').lower()]; g.add((au,RDF.type,CISO.AssetType)); g.add((au,RDFS.label,Literal(asset))); g.add((u,CISO.assetType,au))
    fu=CIS['security-function-'+function.lower()]; g.add((fu,RDF.type,CISO.SecurityFunction)); g.add((fu,RDFS.label,Literal(function))); g.add((u,CISO.securityFunction,fu))
    for ig in sorted(set(igs)):
        iu=CIS[ig.lower()]; g.add((iu,RDF.type,CISO.ImplementationGroup)); g.add((iu,RDFS.label,Literal(ig))); g.add((u,CISO.implementationGroup,iu))
    parsed.append(sid)

if len(parsed)!=153: raise RuntimeError(f'Expected 153 unique safeguards, got {len(parsed)}')
g.serialize(OUT,format='turtle')
print(f'Controls: {len(control_titles)}')
print(f'Safeguards: {len(parsed)}')
print(f'Triples: {len(g)}')
print(OUT)
