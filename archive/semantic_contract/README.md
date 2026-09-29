# Northmart semantic vertical v3

Run:
```bash
python -m pip install -r requirements.txt
python scripts/validate_contract.py
python scripts/generate_ddl.py
python scripts/generate_r2rml.py
```

Sources: enterprise ontology + governance SHACL; CRM local ontology, enterprise alignment, physical model with semantic bindings, and local data SHACL.
Generated artifacts: Databricks DDL/UC tags and R2RML.
