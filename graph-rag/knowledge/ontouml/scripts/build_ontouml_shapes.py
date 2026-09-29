from rdflib import Graph, Namespace, RDF, BNode, Literal
from rdflib.collection import Collection
from rdflib.namespace import XSD
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: python build_ontouml_shapes.py <structured-knowledge-v3.ttl> <shapes.ttl>")

src, out = sys.argv[1], sys.argv[2]
G = Graph().parse(src, format="turtle")
OK = Namespace("https://w3id.org/ontouml/knowledge#")
ONTO = Namespace("https://w3id.org/ontouml#")
SH = Namespace("http://www.w3.org/ns/shacl#")

def local(u):
    return str(u).split("#")[-1].split("/")[-1]

S=Graph()
S.bind("sh",SH); S.bind("ontouml",ONTO); S.bind("ok",OK); S.bind("xsd",XSD)
prefixes=OK.OntoUMLPrefixes
decl=BNode()
S.add((prefixes,SH.declare,decl))
S.add((decl,SH.prefix,Literal("ontouml")))
S.add((decl,SH.namespace,Literal(str(ONTO),datatype=XSD.anyURI)))

def add_target(shape, applies):
    target=BNode()
    S.add((shape,SH.target,target)); S.add((target,RDF.type,SH.SPARQLTarget)); S.add((target,SH.prefixes,prefixes))
    S.add((target,SH.select,Literal(f"""SELECT ?this WHERE {{
  ?this a ontouml:Class ; ontouml:stereotype <{applies}> .
}}""")))

count=0
for c in sorted(set(G.subjects(RDF.type,OK.Constraint)),key=str):
    modality=G.value(c,OK.modality); relation=G.value(c,OK.relation)
    applies=G.value(c,OK.appliesTo); scope=G.value(c,OK.pathScope)
    if modality==OK.Forbidden and relation in (OK.Supertype,OK.Subtype) and applies:
        forbidden=[]
        head=G.value(c,OK.forbiddenTypes)
        if head:
            forbidden=list(Collection(G,head))
        if not forbidden:
            forbidden=[r for r in G.objects(c,OK.references)
                       if str(r).startswith(str(ONTO)) and r!=applies]
            forbidden=list(dict.fromkeys(forbidden))
        if forbidden:
            cid=local(c); shape=OK[f"shape/{cid}"]; add_target(shape,applies)
            S.add((shape,RDF.type,SH.NodeShape)); S.add((shape,OK.implementsConstraint,c)); S.add((c,OK.implementedBy,shape))
            vals=" ".join(f"<{x}>" for x in forbidden)
            direct=scope==OK.Direct
            if relation==OK.Subtype:
                body=("?gen ontouml:specific $this ; ontouml:general ?other ."
                      if direct else "$this (^ontouml:specific/ontouml:general)+ ?other .")
            else:
                body=("?gen ontouml:general $this ; ontouml:specific ?other ."
                      if direct else "$this (^ontouml:general/ontouml:specific)+ ?other .")
            sparql=BNode(); S.add((shape,SH.sparql,sparql)); S.add((sparql,RDF.type,SH.SPARQLConstraint)); S.add((sparql,SH.prefixes,prefixes))
            S.add((sparql,SH.select,Literal(f"""SELECT $this ?other ?forbidden WHERE {{
  {body}
  ?other ontouml:stereotype ?forbidden .
  VALUES ?forbidden {{ {vals} }}
}}""")))
            S.add((sparql,SH.message,Literal(f"{cid}: forbidden OntoUML generalization.")))
            count+=1

for c in sorted(set(G.subjects(RDF.type,OK.Constraint)),key=str):
    if G.value(c,OK.constraintType)!=OK.IdentityProviderConstraint or G.value(c,OK.modality)!=OK.Required:
        continue
    applies=G.value(c,OK.appliesTo); head=G.value(c,OK.allowedIdentityProviders)
    card=G.value(c,OK.cardinality); relation=G.value(c,OK.relation); scope=G.value(c,OK.pathScope)
    if not (applies and head and card and relation==OK.Supertype):
        continue
    allowed=list(Collection(G,head)); cid=local(c); shape=OK[f"shape/{cid}"]; add_target(shape,applies)
    S.add((shape,RDF.type,SH.NodeShape)); S.add((shape,OK.implementsConstraint,c)); S.add((c,OK.implementedBy,shape))
    vals=" ".join(f"<{x}>" for x in allowed)
    path="(^ontouml:specific/ontouml:general)+" if scope==OK.DirectOrIndirect else "^ontouml:specific/ontouml:general"
    sparql=BNode(); S.add((shape,SH.sparql,sparql)); S.add((sparql,RDF.type,SH.SPARQLConstraint)); S.add((sparql,SH.prefixes,prefixes))
    S.add((sparql,SH.select,Literal(f"""SELECT $this WHERE {{
  {{ SELECT $this (COUNT(DISTINCT ?provider) AS ?count) WHERE {{
       $this {path} ?provider .
       ?provider ontouml:stereotype ?providerType .
       VALUES ?providerType {{ {vals} }}
     }} GROUP BY $this }}
  FILTER (?count != {int(card)})
}}""")))
    S.add((sparql,SH.message,Literal(f"{cid}: exactly {int(card)} identity-provider ancestor is required.")))
    count+=1

S.serialize(out,destination=None,format="turtle")
S.serialize(destination=out,format="turtle")
print(f"Generated {count} executable NodeShapes")
print(f"Triples: {len(S)}")
print(f"Output: {out}")
