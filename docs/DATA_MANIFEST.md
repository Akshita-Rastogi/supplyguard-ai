# Data and document manifest

| Asset | Origin | Structure | Stress condition |
|---|---|---|---|
| `world_bank_procurement_regulations_2025.pdf` | World Bank, September 2025 | 154 pages; regulations, annexes and tables | Long-document retrieval and policy hierarchy |
| `world_bank_contract_management_2024.pdf` | World Bank, May/June 2024 | 124 pages; figures, workflows and tables | Figure/table extraction and cross-document retrieval |
| `nist_sp_800_161r1_supply_chain.pdf` | NIST SP 800-161 Rev. 1 Update 1 | 325 pages; dense controls and appendices | Long tables, acronyms and fine-grained citations |
| `fema_disaster_declarations_full.csv` | OpenFEMA v2 | 70,402 data rows, approximately 24 MB | Null dates, booleans, geography, categories and exact MCP computation |

The external snapshots are reproducible samples, not live truth. Production ingestion records retrieval time, upstream version, checksum, validation outcome, and quarantine reason.

## SHA-256 checksums

| Asset | SHA-256 |
|---|---|
| `world_bank_procurement_regulations_2025.pdf` | `7f118ac8fa8949ef23790d84f74c975a98c4bba4effd69328ead58d71578b6f3` |
| `world_bank_contract_management_2024.pdf` | `c37435b2a7cd670a0d8c4f436b2e4252b95350353b4ad90e331f12361b7eae97` |
| `nist_sp_800_161r1_supply_chain.pdf` | `d2bacbf4053adbbe11628f74f071077d8fd59ba99754a3aab34d7813c1cb3d40` |
| `fema_disaster_declarations_full.csv` | `19fb33a4e1a164a986bedc7b138c4f762786fafae56a0ff11d50831cb7f89aa0` |

## Official source URLs

- World Bank regulations: `https://thedocs.worldbank.org/en/doc/c84273d1b230aeb2b0b8134de5dc8cd7-0290012025/original/Procurement-Regulations-7th-Edition-Sep-2025.pdf`
- World Bank contract guidance: `https://thedocs.worldbank.org/en/doc/a5487590ccec42b5709816f40ae8b068-0290012024/original/Contract-Management-Practice-Procurement-Guidance-June-2024-FINAL.pdf`
- NIST SP 800-161r1: `https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-161r1-upd1.pdf`
- FEMA CSV: `https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries.csv`
