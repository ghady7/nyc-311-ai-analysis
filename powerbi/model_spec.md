# Power BI Semantic Model Specification: NYC 311 Analytics

## 1. Data Source Connection
- **Connector**: PostgreSQL
- **Server**: `aws-0-us-east-1.pooler.supabase.com:5432` (or direct: `db.mcuaamgangsjwczggxgj.supabase.co`)
- **Database**: `postgres`
- **Data Connectivity Mode**: **Import Mode** (Required for optimal DAX calculation, fast interactive cross-filtering, and mobile layout support)
- **Tables to Load**:
  1. `dim_agency`
  2. `dim_complaint_type`
  3. `dim_location`
  4. `dim_calendar`
  5. `fact_complaints`
  6. `quarantine_complaints`

---

## 2. Table Relationships (Star Schema)

| From Table (1) | From Column | To Table (*) | To Column | Cardinality | Cross Filter | Active State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `dim_agency` | `agency_key` | `fact_complaints` | `agency_key` | 1 to Many | Single | Active |
| `dim_complaint_type` | `complaint_type_key` | `fact_complaints` | `complaint_type_key` | 1 to Many | Single | Active |
| `dim_location` | `location_key` | `fact_complaints` | `location_key` | 1 to Many | Single | Active |
| `dim_calendar` | `date_key` | `fact_complaints` | `created_date_key` | 1 to Many | Single | **Active** (Default ticket creation timeline) |
| `dim_calendar` | `date_key` | `fact_complaints` | `closed_date_key` | 1 to Many | Single | **Inactive** (Activated via `USERELATIONSHIP`) |
| `quarantine_complaints`| N/A | None | None | **Disconnected** | None | Independent Audit Table |

---

## 3. Columns to Hide from Report View
Hide all surrogate keys and technical foreign keys to prevent business users from misaggregating ID fields:
- `fact_complaints[agency_key]`
- `fact_complaints[complaint_type_key]`
- `fact_complaints[location_key]`
- `fact_complaints[created_date_key]`
- `fact_complaints[closed_date_key]`
- `dim_agency[agency_key]`
- `dim_complaint_type[complaint_type_key]`
- `dim_location[location_key]`
- `dim_calendar[date_key]`
- `quarantine_complaints[quarantine_id]`

---

## 4. Dashboard Pages Blueprint

### Page 1: Ticket Operations & SLA Delays
- **KPI Banner**:
  - Total Complaints (`[Total Complaints]`)
  - Resolution Rate % (`[Resolution Rate %]`)
  - Average Resolution Hours (`[Avg Resolution Hours]`)
  - SLA Compliance Rate % (`[SLA Compliance Rate %]`)
- **Visuals**:
  1. *Stacked Column Chart*: Daily Complaint Volume by Agency (`dim_calendar[full_date]`, `[Total Complaints]`, Legend: `dim_agency[agency_code]`).
  2. *Horizontal Bar Chart*: Top 10 Complaint Types by Avg Resolution Hours (`dim_complaint_type[complaint_type]`, `[Avg Resolution Hours]`).
  3. *Filled Map / Shape Map*: Complaint Density & Resolution Time by Borough (`dim_location[borough]`, `[Total Complaints]`, Color: `[Avg Resolution Hours]`).
  4. *Donut Chart*: Ingestion Channel Breakdown (`fact_complaints[open_data_channel_type]`, `[Total Complaints]`).
  5. *Slicers*: Borough (`dim_location[borough]`), Agency (`dim_agency[agency_code]`), Date Range (`dim_calendar[full_date]`).

### Page 2: Pipeline Health & Data Quarantine
- **KPI Banner**:
  - Raw Records Evaluated (`[Raw Complaints Evaluated]`)
  - Production Clean Records (`[Total Complaints]`)
  - Quarantined Records (`[Quarantined Complaints]`)
  - Pipeline Pass Rate % (`[Pipeline Data Pass Rate %]`)
- **Visuals**:
  1. *Donut Chart*: Quarantine Breakdown by Rejection Reason (`quarantine_complaints[rejection_reason]`, `[Quarantined Complaints]`).
  2. *Card / Gauge*: Pipeline Health Score (`[Pipeline Data Pass Rate %]`, Target: 99.5%).
  3. *Table Visual*: Granular Quarantine Audit Log (`quarantine_complaints[unique_key]`, `rejection_reason`, `created_date`, `closed_date`, `agency`, `borough`, `incident_zip`, `raw_resolution_hours`).
