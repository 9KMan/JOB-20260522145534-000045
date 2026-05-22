# SPEC: Senior DOMO Data Engineer — Week-over-Week Reporting Restoration

## 1. Project Overview

**Client:** Upwork — existing DOMO BI environment needing ETL audit and repair
**Goal:** Restore reliable week-over-week reporting by aligning DOMO dashboard metrics with official weekly scorecard data, identifying root causes of data discrepancies, and improving ETL structure for consistency, traceability, and reusability.
**Stack:** DOMO (Magic ETL, Dataflows, Workbench), SQL, Python, JSON/Lookup datasets, Beast Mode, DOMO API.

---

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     SOURCE SYSTEMS                               │
│  ERP / CRM / Database → DOMO Workbench → DOMO DataSets         │
│  Weekly Scorecard (official source of truth)                     │
└────────────────────────┬─────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│              DOMO MAGIC ETL (Dataflows)                          │
│  • Input: Raw DataSets (ERP/CRM/External)                        │
│  • Transform: Join, Filter, Group By, Rank                      │
│  • Output: Refined DataSets → DOMO Cards/Dashboards             │
│                                                                  │
│  KNOWN ISSUES:                                                   │
│  ⚠ Metrics not aligned with weekly scorecard definitions        │
│  ⚠ Duplicate/conflicting transformations across dataflows       │
│  ⚠ No audit trail for metric lineage                             │
│  ⚠ Reuse across dashboards = copy-paste = drift                 │
└────────────────────────┬─────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                  DOMO DASHBOARDS                                │
│  Weekly Scorecard → KPIs vs Dashboard Cards (discrepancy audit) │
│  • Identify which cards reference which dataset/dataflow         │
│  • Compare aggregations to source scorecard totals              │
│  • Flag Beast Mode formulas that diverge from business logic    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Workstreams

### 3.1 DOMO Environment Audit
- Inventory all existing DataSets, Dataflows, and Cards in the DOMO instance
- Map data lineage: which card uses which dataset → which dataflow → which source table
- Identify duplicate/redundant dataflows doing similar transformations
- Document current ETL structure (text-based diagram for each dataflow)

### 3.2 Metric Alignment — Week-over-Week Scorecard
- Receive or extract the "official weekly scorecard" data (the source of truth)
- Import into DOMO as a Lookup/Reference dataset
- For each KPI on the scorecard, trace backward: card → dataflow → dataset → source
- Calculate the KPI value in the scorecard vs the value shown on the dashboard
- **Discrepancy report:** One row per divergent metric with: card name, current value, expected value, % variance, likely root cause

### 3.3 Root Cause Analysis & Fix
- **Common DOMO discrepancy causes:**
  1. Beast Mode formula using different date filter (relative vs absolute)
  2. Dataflow join type mismatch (LEFT vs INNER — different rows included)
  3. Date partitioning: scorecard uses Monday-Sunday week, DOMO uses Sunday-Saturday (or vice versa)
  4. Aggregation level: scorecard at company level vs card at region-level with unweighted totals
  5. Stale data: dataflow last-run time vs scorecard refresh schedule
  6. Lookup dataset not refreshed — old reference data causing wrong joins
- For each discrepancy: document root cause, propose fix, estimate effort

### 3.4 ETL Restructuring — Reusable Metric Layer
- Design a "Metric Store" pattern: one canonical DataFlow per business metric
- Inputs: raw source datasets
- Transformations: business logic (e.g., `total_revenue = SUM(gross_sales) - SUM(returns)`)
- Output: a `metrics_lookup` dataset consumed by all cards
- Benefits: single source of truth, one fix propagates everywhere, audit trail clear
- Implement 3-5 pilot metrics from the weekly scorecard using this pattern

### 3.5 Governance & Traceability
- Document all metrics with: definition, formula, data source, owner, refresh schedule
- Add DOMO Dataset descriptions (metadata field) — often left blank = zero discoverability
- Tag DataFlows with category + owner (DOMO DataFlow tags)
- Add a "metrics dictionary" DOMO dataset that cards can reference

---

## 4. Data Model

### Metric Reconciliation Table
```
| metric_name | card_name | dashboard | current_value | expected_value | variance_pct | root_cause | fix_status |
```

### DOMO DataFlow Lineage Map
```
[Source Table] → [Workbench Connection] → [DataSet] → [Magic ETL DataFlow] → [Output DataSet] → [Card]
                                   ↑                              ↑
                         (intermediate datasets)       (reusable metric layer)
```

### Recommended Metric Store Schema
```
metrics_store: { metric_key, metric_name, metric_value, dimension_week, dimension_region, etl_timestamp }
```

---

## 5. Technical Decisions

1. **Magic ETL over SQL DataFlows** — Visual, easier for client to audit and modify post-engagement
2. **Metric Store pattern** — One canonical dataflow per metric, consumed by all cards. Eliminates copy-paste drift.
3. **Weekly scorecard as Lookup dataset** — Import as a static/reference dataset; join to raw data to verify reconciliation
4. **Beast Mode for display-layer calculations** — Move complex logic out of dataflow into Beast Mode for transparency
5. **DOMO API for audit automation** — Use `pydomo` or direct API calls to extract full inventory (datasets, dataflows, cards) programmatically, rather than manual screenshot audit
6. **Contract-to-hire scope** — Fix the immediate discrepancies first (quick wins), then restructure ETL foundation (Phase 2)

---

## 6. Out of Scope
- New data sources beyond what currently feeds DOMO
- Building new dashboards from scratch (restoring existing, not creating new)
- DOMO infrastructure setup (instance already configured)
- Mobile app or embedding configurations

---

## 7. Success Metrics
- 100% of scorecard KPIs reconciled — no undefined discrepancies remaining
- All dashboards showing same values as official weekly scorecard (verified manually)
- ETL restructuring: pilot 5 metrics using Metric Store pattern
- Full metric lineage documented (which card → which dataflow → which source)