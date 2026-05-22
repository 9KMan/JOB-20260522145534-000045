# SPEC: Senior DOMO Data Engineer — Week-over-Week Reporting Restoration

## 🚀 Quick Start

> **Note:** DOMO is a cloud BI platform — there is no local Docker deployment. The quick start below applies to the **Python DOMO audit toolkit** included in this repo.

```bash
# Clone & Run in 3 commands
git clone https://github.com/9KMan/JOB-20260522145534-000045
cd JOB-20260522145534-000045 && pip install -r requirements.txt
# Configure: set DOMO_INSTANCE, DOMO_TOKEN in .env
python domo_audit.py --list-datasets
```

---

## 1. Project Overview

**Client:** Upwork — existing DOMO BI environment needing ETL audit and repair
**Goal:** Restore reliable week-over-week reporting by aligning DOMO dashboard metrics with official weekly scorecard data, identifying root causes of data discrepancies, and improving ETL structure for consistency, traceability, and reusability.
**Stack:** DOMO (Magic ETL, Dataflows, Workbench), SQL, Python, JSON/Lookup datasets, Beast Mode, DOMO API (pydomo).

**Contract Type:** Contract-to-hire (6+ months, 20-25 hrs/week → potential full-time conversion)

---

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     SOURCE SYSTEMS                               │
│  ERP / CRM / Database → DOMO Workbench → DOMO DataSets        │
│  Weekly Scorecard (official source of truth)                     │
└────────────────────────┬─────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│              DOMO MAGIC ETL (Dataflows)                         │
│  • Input: Raw DataSets (ERP/CRM/External)                       │
│  • Transform: Join, Filter, Group By, Rank, Add Formula        │
│  • Output: Refined DataSets → DOMO Cards/Dashboards             │
│                                                                   │
│  KNOWN ISSUES:                                                    │
│  • Metrics not aligned with weekly scorecard definitions         │
│  • Duplicate/conflicting transformations across dataflows        │
│  • No audit trail for metric lineage                             │
│  • Reuse across dashboards = copy-paste = drift                  │
└────────────────────────┬─────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                  DOMO DASHBOARDS                                 │
│  Weekly Scorecard → KPIs vs Dashboard Cards (discrepancy audit) │
│  • Identify which cards reference which dataset/dataflow         │
│  • Compare aggregations to source scorecard totals               │
│  • Flag Beast Mode formulas that diverge from business logic     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Workstreams

### 3.1 DOMO Environment Audit
- Inventory all existing DataSets, DataFlows, and Cards in the DOMO instance using pydomo API
- Map data lineage: which card uses which dataset → which dataflow → which source table
- Identify duplicate/redundant dataflows doing similar transformations
- Document current ETL structure with text-based diagrams for each dataflow
- Output: CSV/Google Sheet with full inventory (name, type, owner, last run, upstream deps, downstream consumers)

### 3.2 Metric Alignment — Week-over-Week Scorecard Reconciliation
- Receive or extract the "official weekly scorecard" data as the source of truth
- Import scorecard into DOMO as a Lookup/Reference dataset with week-ending date as the key
- For each KPI on the scorecard, trace backward: card → dataflow → dataset → source table
- Calculate the KPI value in the scorecard vs the value shown on each dashboard card
- Produce a Discrepancy Report: one row per divergent metric with card name, current value, expected value, % variance, and likely root cause
- Prioritize discrepancies by business impact (revenue-affecting metrics first)

### 3.3 Root Cause Analysis & Fix (Top Discrepancies)
Common DOMO discrepancy causes with specific fix strategies:
- **Beast Mode date filter mismatch:** Scorecard uses ISO week (Monday start, WEEK(date,1)) vs DOMO default (Sunday start, WEEK(date,0)). Fix: update Beast Mode to use ISO week equivalent.
- **Magic ETL join type mismatch:** LEFT JOIN vs INNER JOIN — different row counts included. Fix: review join cardinality and correct join type in Magic ETL.
- **Date partitioning alignment:** Scorecard uses Monday-Sunday week, DOMO uses Sunday-Saturday. Fix: add Date Filter tile or Beast Mode WEEK() override.
- **Aggregation level mismatch:** Scorecard at company total; card shows SUM of region values where NULL regions are excluded (not treated as 0). Fix: use COALESCE in Beast Mode.
- **Dataflow staleness:** DataFlow last-run time is before scorecard generation time. Fix: check dataflow.last_run via DOMO API, schedule more frequent refreshes.
- **Lookup dataset not refreshed:** Static reference data causing wrong joins. Fix: verify lookup dataset refresh schedule.
- **One-to-many join duplication:** Duplicate rows because of multiple line items per header record. Fix: deduplicate upstream in Magic ETL Group By on the primary key.

For each discrepancy: document root cause, propose fix, estimate effort, implement.

### 3.4 ETL Restructuring — Reusable Metric Store Pattern
Design and implement a "Metric Store" layer:
- One canonical Magic ETL DataFlow or SQL DataFlow per business metric
- Input: raw source datasets only
- Transformation: one and only one business logic rule per DataFlow
- Output: a `metrics_store` dataset consumed by all downstream cards
- Benefits: single source of truth, one fix propagates everywhere, audit trail clear
- Implement 3-5 pilot metrics from the weekly scorecard using this pattern first
- Migrate 2-3 priority dashboards to consume from metrics_store instead of raw dataflows

### 3.5 Governance & Traceability
- Document all metrics with: definition, formula (Beast Mode or SQL), data source, owner, refresh schedule, last verified date
- Populate DOMO Dataset descriptions (metadata field) — currently blank = zero discoverability
- Tag DataFlows with category and owner using DOMO DataFlow tags
- Create a "metrics_dictionary" DOMO dataset that cards can reference for definitions
- Set up automated audit report via DOMO API (weekly run: compare scorecard to DOMO KPIs, alert on variance > 1%)

---

## 4. Data Model

### Metric Reconciliation Table (Discrepancy Report)
| metric_name | card_name | dashboard | scorecard_value | domo_value | variance_pct | root_cause | fix_status |
|-------------|-----------|-----------|-----------------|------------|--------------|------------|------------|

### DOMO DataFlow Lineage Map
```
[Source Table] → [Workbench Connection] → [DataSet] → [Magic ETL DataFlow] → [Output DataSet] → [Card]
                                    ↑                             ↑
                          (intermediate datasets)      (reusable metric layer)
```

### Recommended Metric Store Schema
```sql
metrics_store: {
  metric_key: VARCHAR,      -- e.g., 'weekly_revenue', 'active_deals_count'
  metric_name: VARCHAR,      -- business-friendly name
  metric_value: DECIMAL,     -- the calculated value
  dimension_week: DATE,      -- ISO week ending (Monday)
  dimension_region: VARCHAR, -- region/dimension breakdown
  etl_timestamp: TIMESTAMP,  -- when this was calculated
  dataflow_id: VARCHAR,      -- which dataflow produced this
  verified: BOOLEAN          -- has this been checked against scorecard
}
```

### Audit Log Schema
```sql
audit_log: {
  run_id: UUID,
  metric_key: VARCHAR,
  scorecard_value: DECIMAL,
  domo_value: DECIMAL,
  variance_pct: DECIMAL,
  fix_applied: TEXT,
  fixed_by: VARCHAR,
  fixed_at: TIMESTAMP
}
```

---

## 5. Technical Decisions

1. **Magic ETL over SQL DataFlows** — Visual, easier for client to audit and modify post-engagement without deep SQL knowledge. Exception: complex aggregations for Metric Store may use SQL DataFlow.

2. **Metric Store pattern** — One canonical DataFlow per metric, consumed by all cards. Eliminates copy-paste drift. Every VP sees the same numbers because there's only one definition of each metric.

3. **Weekly scorecard as Lookup dataset** — Import as a static/reference dataset. Join to raw data to verify reconciliation. Refresh schedule must match scorecard publication schedule.

4. **Beast Mode for display-layer calculations** — Move complex logic out of dataflow into Beast Mode for transparency and easier auditing by business users.

5. **DOMO API for audit automation (pydomo)** — Extract full inventory programmatically: list all datasets, dataflows, cards, last run times. Manual screenshot audit is error-prone and slow.

6. **Contract-to-hire scope discipline** — Fix immediate discrepancies first (quick wins, hours 1-40). ETL restructuring is Phase 2. Earn the conversion by showing measurable impact early.

---

## 6. Out of Scope
- New data sources beyond what currently feeds DOMO
- Building new dashboards from scratch (restoring existing, not creating new)
- DOMO infrastructure setup (instance already configured)
- Mobile app or embedding configurations
- SSO/security configuration changes
- ETL transformation development for new metrics (only remediation of existing broken metrics)

---

## 7. Success Metrics
- 100% of scorecard KPIs reconciled — zero undefined discrepancies
- All dashboards showing same values as official weekly scorecard (verified manually after fixes)
- ETL restructuring: pilot 5 metrics using Metric Store pattern deployed
- Full metric lineage documented (which card → which dataflow → which source)
- Automated weekly audit report running via DOMO API
- Contract-to-hire conversion: Phase 1 complete → Phase 2 engagement confirmed