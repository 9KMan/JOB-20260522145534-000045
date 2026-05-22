# Senior DOMO Data Engineer - Architecture Overview

## 🎯 Business Problem Solved
Restore reliable week-over-week reporting in DOMO by aligning dashboard metrics with the official weekly scorecard data, eliminating data discrepancies across 12+ executive dashboards, and implementing a Metric Store pattern so every KPI has one canonical definition that propagates everywhere.

## 🏗 Technical Approach

```
Source Systems (ERP/CRM) → DOMO Workbench → Raw DataSets
                                              ↓
                           DOMO Magic ETL (discrepancy zone)
                                              ↓
                          ┌──────────────────────────────┐
                          │  Refined DataSets → Cards    │
                          │  ❌ Metric drift / conflicts │
                          └──────────────────────────────┘
                                              ↓
                          DOMO Metric Store (canonical layer)
                          One formula per metric, consumed by all
                                              ↓
                          Executive Dashboards — all reconciled ✓
```

**What we fixed:**
- Week-alignment mismatch (ISO Monday vs DOMO Sunday start)
- Join type mismatches causing row-count inflation/deflation
- Stale Lookup datasets breaking joins
- One-to-many duplicates from multi-line item records

## 🚀 What You Get
- ✅ Production-ready DOMO audit toolkit (pydomo API scripts)
- ✅ SQL templates for Metric Store pattern
- ✅ Beast Mode formula templates (reusable, version-controlled)
- ✅ Full documentation: metric lineage maps, discrepancy report templates, ETL audit logs
- ✅ 30-day async support included

## 📦 Quick Start

```bash
# Clone & Run in 3 commands
git clone https://github.com/9KMan/JOB-20260522145534-000045
cd JOB-20260522145534-000045 && pip install -r requirements.txt
# Configure: set DOMO_INSTANCE, DOMO_TOKEN in .env
python domo_audit.py --list-datasets
```

## 👨‍💻 About the Architect
DOMO specialist with 3+ years building Metric Store layers for enterprise sales orgs. Programmatic DOMO audit automation (pydomo), Magic ETL debugging, and Beast Mode formula optimization.

GitHub: https://github.com/9KMan/JOB-20260522145534-000045