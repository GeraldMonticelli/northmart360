# CyFun 2025 operational crosswalk RDF

Source: `CyFun2025_mapping_2026-05-WIP.xlsx`.

Operational target frameworks retained:
- ISO/IEC 27002:2022
- CIS Controls v8.1
- IEC 62443-2-1:2024
- IEC 62443-3-3:2013

ISO/IEC 27001 and NIS2 legal mappings are intentionally kept out of this operational-control layer; they can be represented later as governance/regulatory traceability layers.

## Fidelity rule
The spreadsheet sometimes places multiple CyFun requirements (Basic / Important / Essential) on the same row while exposing a single mapping cell for a target framework. The RDF therefore reifies the published **row-level mapping assertion**, attaches all CyFun requirements present on that row, preserves the original cell text, row and cell coordinates, and marks such assertions `map:mappingGranularity "row-shared"`. It does not claim exact one-to-one equivalence.

Statistics:
- mapping assertions: 565
- CyFun requirements participating: 216
- distinct target references: 234
- assertion → target links: 1366
- source rows containing multiple CyFun requirements: 49
- assertions by framework: {'ISO/IEC 27002:2022': 158, 'CIS Controls v8.1': 151, 'IEC 62443-2-1:2024': 154, 'IEC 62443-3-3:2013': 102}
