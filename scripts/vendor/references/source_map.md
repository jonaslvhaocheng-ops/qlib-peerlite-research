# Source map

Evidence cutoff: 2026-07-27. Living pages are identified as such; a retrieval date is not a substitute for a vendor data-version receipt.

| ID | Primary source | Version / date | What it supports | Checks |
|---|---|---|---|---|
| SM01 | [W3C PROV-DM](https://www.w3.org/TR/2013/REC-prov-dm-20130430/) | W3C Recommendation, 2013-04-30 | Entities, activities, agents, derivation and valid provenance-time relations | I001, I002 |
| SM02 | [FAIR Guiding Principles](https://doi.org/10.1038/sdata.2016.18) | Scientific Data 3:160018, 2016 | Persistent identifiers, rich metadata, vocabularies, provenance and domain standards | I001, S001 |
| SM03 | [SEC Webmaster FAQ — EDGAR timestamps](https://www.sec.gov/about/webmaster-frequently-asked-questions) | Living SEC documentation; retrieved 2026-07-26 | Report period, filed date, change date and acceptance timestamp are distinct; SEC exposes no exact first-web-availability timestamp | T001, T002, T003 |
| SM04 | [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | Living SEC documentation; retrieved 2026-07-26 | Dissemination schedules, next-business-day cases, accession identifiers and issuer-name changes | T002, M001 |
| SM05 | [SEC Correct or Delete a Filing](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/correct-or-delete-filing) | 2024-06-04 | Original and amended filings normally remain separate public records | T003 |
| SM06 | [IANA Time Zone Database](https://www.iana.org/time-zones) | tzdb 2026c, released 2026-07-08 | Versioned historical UTC offsets and daylight-saving rules | T001, C001 |
| SM07 | [Microsoft Qlib PIT documentation](https://github.com/microsoft/qlib/blob/v0.9.7/docs/advanced/PIT.rst) | Qlib v0.9.7; retrieved 2026-07-26 | Publication date and reporting period must be preserved across statement revisions | T003 |
| SM08 | [FRED API Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) and [vintage dates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html) | FRED API v1 living docs; retrieved 2026-07-26 | “Known as of” differs from observation date; releases and revisions have vintages | T003 |
| SM09 | [S&P DJI Index Governance Policies](https://www.spglobal.com/spdji/en/documents/index-policies/sp-index-governance-policies.pdf) | May 2026 | Index changes have announcement and implementation dates; methodologies can change | U001 |
| SM10 | [MSCI Global Investable Market Indexes Methodology](https://www.msci.com/eqb/methodology/meth_docs/MSCI_GIMIMethodology_May2026.pdf) | May 2026 | Review data cutoffs, announcements, effective dates and pre-implementation amendments are distinct | U001 |
| SM11 | [CRSP Market Indexes Methodology Guide](https://www.crsp.org/wp-content/uploads/guides/CRSP_Market_Indexes_Methodology_Guide.pdf) | July 2026; modified 2026-07-01 | Eligible-universe construction, delists, suspended securities, corporate actions, late information and valuation order | U002, A001 |
| SM12 | [Shumway, “The Delisting Bias in CRSP Data”](https://doi.org/10.1111/j.1540-6261.1997.tb03818.x) | Journal of Finance 52(1), 1997 | Missing negative delisting returns can materially bias historical return studies | U002 |
| SM13 | [NYSE Holidays & Trading Hours](https://www.nyse.com/trade/hours-calendars) | Living exchange calendar; retrieved 2026-07-26 | Product-specific sessions, holidays and early closes | C001 |
| SM14 | [Nasdaq Current Trading Halts](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHalts) and [Halt History](https://www.nasdaqtrader.com/trader.aspx?id=TradingHaltHistory) | Living exchange records; retrieved 2026-07-26 | Halt state and time are separate market facts requiring historical treatment | H001 |
| SM15 | [PostgreSQL 18 Constraints](https://www.postgresql.org/docs/18/ddl-constraints.html) | PostgreSQL 18 | A declared single or composite primary key must be unique and non-null | Q001 |
| SM16 | [TensorFlow Data Validation anomaly reference](https://www.tensorflow.org/tfx/data_validation/anomalies) | Living TFX docs; retrieved 2026-07-26 | Schema/statistics comparisons detect missing, type and domain anomalies | Q002, Q003 |
| SM17 | [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) | scikit-learn 1.9.0 docs; retrieved 2026-07-26 | Time-ordered splits avoid training on the future; a gap can separate folds | L002 |
| SM18 | [López de Prado, Advances in Financial Machine Learning](https://www.oreilly.com/library/view/advances-in-financial/9781119482086/p01.xhtml) | Wiley, 2018, chapters 4 and 7 | Overlapping outcomes and purged cross-validation are separate concerns | L002 |
| SM19 | [Morningstar/CRSP PERMNO & PERMCO](https://indexes.morningstar.com/research-data-products/permno) | Living product documentation; retrieved 2026-07-26 | Permanent security/company identifiers persist through lifecycle and corporate-identity changes | M001 |
| SM20 | [Morningstar/CRSP Research Data Products Document Library](https://indexes.morningstar.com/research-data-products/document-library) | CRSP US Stock Databases Data Descriptions Guide for CRSPAccess FIZ, 2026-06-30 | Raw/adjusted field definitions, distribution adjustments and adjustment bases | A001 |
| SM21 | [Feast point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) | Living official documentation; retrieved 2026-07-27 | Historical feature retrieval must join each entity row to feature values available at that row's timestamp rather than to the current state | B003, B004 |
| SM22 | [OpenLineage object model](https://openlineage.io/docs/1.30.0/spec/object-model) | OpenLineage 1.30 object model; retrieved 2026-07-27 | Dataset, job and run identities plus version and source-code facets can bind how an output was derived from exact inputs | B001, B002 |
| SM23 | [Apache Iceberg time-travel queries](https://iceberg.apache.org/docs/nightly/spark-queries/) | Official nightly documentation; retrieved 2026-07-27 | Snapshot IDs and historical table versions can identify a reproducible source state; retention remains a separate requirement | B001, B002 |

## Source-use boundary

- These sources justify audit principles, not the truth of a supplied dataset.
- Vendor manuals must match the exact product, field edition and extract version under audit.
- Marketing claims, GitHub stars and secondary blog summaries are not evidence.
- A live URL without an immutable revision is recorded as contextual evidence only; the audit still needs the supplied file/hash/version receipt.
