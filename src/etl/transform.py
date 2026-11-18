"""
NYC 311 Service Requests Transformation & Quarantine Engine
Executes Gate 2 cleaning, anomaly quarantine routing, Parquet export,
and mathematical reconciliation reporting.
"""

import os
import glob
import sys
import duckdb
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def get_latest_raw_file() -> str:
    """Retrieve the latest compressed raw JSON file."""
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
    pattern = os.path.join(raw_dir, "raw_311_*.json.gz")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No raw files found matching {pattern}")
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def run_transformation():
    raw_path = get_latest_raw_file()
    norm_raw = raw_path.replace("\\", "/")
    
    clean_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "clean"))
    quarantine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "quarantine"))
    os.makedirs(clean_dir, exist_ok=True)
    os.makedirs(quarantine_dir, exist_ok=True)

    clean_parquet = os.path.join(clean_dir, "clean_complaints.parquet").replace("\\", "/")
    quarantine_parquet = os.path.join(quarantine_dir, "quarantine_complaints.parquet").replace("\\", "/")
    quarantine_csv = os.path.join(quarantine_dir, "quarantine_complaints.csv").replace("\\", "/")
    reconciliation_xlsx = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "qa_reconciliation.xlsx"))

    print("=" * 70, flush=True)
    print("GATE 2 TRANSFORMATION & RECONCILIATION PIPELINE", flush=True)
    print(f"Source Raw Artifact:       {norm_raw}", flush=True)
    print(f"Target Clean Parquet:      {clean_parquet}", flush=True)
    print(f"Target Quarantine Parquet: {quarantine_parquet}", flush=True)
    print(f"Audit Reconciliation Xlsx: {reconciliation_xlsx}", flush=True)
    print("=" * 70 + "\n", flush=True)

    con = duckdb.connect(database=":memory:")

    # 1. Materialize Staging Table in Memory ONCE
    print("Materializing raw records into memory and evaluating anomaly flags...", flush=True)
    create_staging_table_sql = f"""
    CREATE TABLE staged_evaluation AS
    SELECT 
        *,
        CASE 
            WHEN closed_date IS NOT NULL AND TRY_CAST(closed_date AS TIMESTAMP) < TRY_CAST(created_date AS TIMESTAMP) 
                THEN 'CHRONOLOGY_VIOLATION'
            WHEN borough IS NULL OR TRIM(borough) IN ('', 'Unspecified') 
                THEN 'UNASSIGNED_BOROUGH'
            WHEN incident_zip IS NOT NULL AND (TRY_CAST(TRIM(incident_zip) AS INTEGER) < 10001 OR TRY_CAST(TRIM(incident_zip) AS INTEGER) > 11697) 
                THEN 'INVALID_OR_OUT_OF_STATE_ZIP'
            ELSE NULL 
        END AS rejection_reason,
        CASE 
            WHEN closed_date IS NOT NULL THEN 
                date_diff('second', TRY_CAST(created_date AS TIMESTAMP), TRY_CAST(closed_date AS TIMESTAMP)) / 3600.0
            ELSE NULL 
        END AS calc_res_hours
    FROM read_ndjson('{norm_raw}');
    """
    con.execute(create_staging_table_sql)
    print("Staging table created successfully.", flush=True)

    # 2. Export Quarantined Records
    print("Exporting Quarantined Records to Parquet & CSV...", flush=True)
    export_quarantine_sql = f"""
    COPY (
        SELECT 
            unique_key,
            created_date,
            closed_date,
            agency,
            agency_name,
            complaint_type,
            descriptor,
            incident_zip,
            borough,
            city,
            status,
            rejection_reason,
            ROUND(calc_res_hours, 2) AS raw_resolution_hours,
            CURRENT_TIMESTAMP AS quarantined_at
        FROM staged_evaluation
        WHERE rejection_reason IS NOT NULL
        ORDER BY rejection_reason, unique_key
    ) TO '{quarantine_parquet}' (FORMAT PARQUET);
    """
    con.execute(export_quarantine_sql)

    con.execute(f"""
    COPY (SELECT * FROM read_parquet('{quarantine_parquet}')) TO '{quarantine_csv}' (HEADER, DELIMITER ',');
    """)
    print("Quarantined records exported.", flush=True)

    # 3. Export Clean Records
    print("Exporting Clean Records to Parquet...", flush=True)
    export_clean_sql = f"""
    COPY (
        SELECT 
            unique_key,
            TRY_CAST(created_date AS TIMESTAMP) AS created_date,
            TRY_CAST(closed_date AS TIMESTAMP) AS closed_date,
            CASE 
                WHEN closed_date IS NOT NULL THEN ROUND(calc_res_hours, 2)
                ELSE NULL 
            END AS resolution_hours,
            TRIM(UPPER(agency)) AS agency,
            TRIM(agency_name) AS agency_name,
            TRIM(complaint_type) AS complaint_type,
            TRIM(descriptor) AS descriptor,
            COALESCE(TRIM(location_type), 'Unspecified') AS location_type,
            COALESCE(TRIM(incident_zip), 'UNKNOWN') AS incident_zip,
            TRIM(incident_address) AS incident_address,
            TRIM(street_name) AS street_name,
            COALESCE(TRIM(address_type), 'UNKNOWN') AS address_type,
            COALESCE(NULLIF(TRIM(UPPER(city)), ''), TRIM(UPPER(borough))) AS city,
            TRIM(landmark) AS landmark,
            TRIM(facility_type) AS facility_type,
            CASE 
                WHEN TRIM(status) = 'Unspecified' THEN 'Open'
                ELSE TRIM(status) 
            END AS status,
            TRY_CAST(due_date AS TIMESTAMP) AS due_date,
            TRIM(resolution_description) AS resolution_description,
            TRY_CAST(resolution_action_updated_date AS TIMESTAMP) AS resolution_action_updated_date,
            TRIM(community_board) AS community_board,
            TRIM(bbl) AS bbl,
            TRIM(UPPER(borough)) AS borough,
            COALESCE(TRIM(UPPER(open_data_channel_type)), 'UNKNOWN') AS open_data_channel_type,
            TRY_CAST(latitude AS DOUBLE) AS latitude,
            TRY_CAST(longitude AS DOUBLE) AS longitude,
            TRY_CAST(x_coordinate_state_plane AS DOUBLE) AS x_coordinate,
            TRY_CAST(y_coordinate_state_plane AS DOUBLE) AS y_coordinate,
            EXTRACT(YEAR FROM TRY_CAST(created_date AS TIMESTAMP)) AS created_year,
            EXTRACT(MONTH FROM TRY_CAST(created_date AS TIMESTAMP)) AS created_month,
            EXTRACT(DAY FROM TRY_CAST(created_date AS TIMESTAMP)) AS created_day,
            EXTRACT(HOUR FROM TRY_CAST(created_date AS TIMESTAMP)) AS created_hour,
            EXTRACT(DOW FROM TRY_CAST(created_date AS TIMESTAMP)) AS created_dow,
            CASE WHEN closed_date IS NOT NULL THEN TRUE ELSE FALSE END AS is_closed
        FROM staged_evaluation
        WHERE rejection_reason IS NULL
        ORDER BY created_date DESC
    ) TO '{clean_parquet}' (FORMAT PARQUET);
    """
    con.execute(export_clean_sql)
    print("Clean records exported.", flush=True)

    # 4. Extract Reconciliation Metrics
    print("Calculating Reconciliation Proof Metrics...", flush=True)
    recon_df = con.execute("""
    SELECT 
        'Raw Source (Socrata)' AS cohort,
        COUNT(*) AS total_rows,
        COUNT(calc_res_hours) AS closed_tickets,
        ROUND(SUM(calc_res_hours), 2) AS sum_resolution_hours,
        ROUND(AVG(calc_res_hours), 2) AS avg_resolution_hours
    FROM staged_evaluation
    UNION ALL
    SELECT 
        'Clean Staging (Warehouse-Ready)',
        COUNT(*),
        COUNT(calc_res_hours),
        ROUND(SUM(calc_res_hours), 2),
        ROUND(AVG(calc_res_hours), 2)
    FROM staged_evaluation WHERE rejection_reason IS NULL
    UNION ALL
    SELECT 
        'Quarantine (Rejected / Anomalous)',
        COUNT(*),
        COUNT(calc_res_hours),
        ROUND(SUM(calc_res_hours), 2),
        ROUND(AVG(calc_res_hours), 2)
    FROM staged_evaluation WHERE rejection_reason IS NOT NULL;
    """).df()

    reason_df = con.execute("""
    SELECT 
        rejection_reason,
        COUNT(*) AS rejected_count,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM staged_evaluation WHERE rejection_reason IS NOT NULL), 2) AS pct_of_quarantine,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM staged_evaluation), 3) AS pct_of_raw
    FROM staged_evaluation
    WHERE rejection_reason IS NOT NULL
    GROUP BY rejection_reason
    ORDER BY rejected_count DESC;
    """).df()

    sample_q_df = con.execute("""
    SELECT 
        unique_key,
        rejection_reason,
        created_date,
        closed_date,
        agency,
        complaint_type,
        borough,
        incident_zip,
        status,
        raw_resolution_hours
    FROM read_parquet('""" + quarantine_parquet + """')
    ORDER BY rejection_reason, unique_key;
    """).df()

    print("\n--- RECONCILIATION PROOF TABLE ---", flush=True)
    print(recon_df.to_string(index=False), flush=True)
    print("\n--- QUARANTINE BREAKDOWN BY REJECTION REASON ---", flush=True)
    print(reason_df.to_string(index=False), flush=True)

    # 5. Build Formatted QA Audit Workbook
    print(f"\nGenerating QA Reconciliation Workbook: {reconciliation_xlsx} ...", flush=True)
    wb = openpyxl.Workbook()
    ws_summary = wb.active
    ws_summary.title = "Reconciliation_Proof"

    # Styling definitions
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", size=10, bold=True)
    thin_border = Border(
        left=Side(style='thin', color="D9D9D9"),
        right=Side(style='thin', color="D9D9D9"),
        top=Side(style='thin', color="D9D9D9"),
        bottom=Side(style='thin', color="D9D9D9")
    )

    # Title block
    ws_summary.cell(row=1, column=1, value="NYC 311 ANALYTICS PIPELINE - GATE 2 MATHEMATICAL RECONCILIATION").font = Font(name="Calibri", size=14, bold=True, color="1F497D")
    ws_summary.cell(row=2, column=1, value=f"Source: {norm_raw} | Verified Mathematical Equality: Raw == Clean + Quarantined").font = Font(name="Calibri", size=10, italic=True)

    # Table 1: Mathematical Reconciliation
    headers1 = ["Cohort", "Total Rows", "Closed Tickets", "Sum Resolution Hours", "Avg Resolution Hours"]
    for col_idx, h in enumerate(headers1, 1):
        c = ws_summary.cell(row=4, column=col_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    for r_idx, row in recon_df.iterrows():
        row_num = 5 + r_idx
        ws_summary.cell(row=row_num, column=1, value=row["cohort"]).font = bold_font if r_idx == 0 else data_font
        ws_summary.cell(row=row_num, column=2, value=int(row["total_rows"])).number_format = "#,##0"
        ws_summary.cell(row=row_num, column=3, value=int(row["closed_tickets"])).number_format = "#,##0"
        ws_summary.cell(row=row_num, column=4, value=float(row["sum_resolution_hours"])).number_format = "#,##0.00"
        ws_summary.cell(row=row_num, column=5, value=float(row["avg_resolution_hours"])).number_format = "#,##0.00"
        for c_idx in range(1, 6):
            ws_summary.cell(row=row_num, column=c_idx).border = thin_border

    # Table 2: Quarantine Breakdown
    start_r2 = 10
    ws_summary.cell(row=start_r2 - 1, column=1, value="Quarantine Classification Summary").font = Font(name="Calibri", size=12, bold=True, color="1F497D")
    headers2 = ["Rejection Reason", "Rejected Record Count", "% of Quarantined", "% of Raw Data"]
    for col_idx, h in enumerate(headers2, 1):
        c = ws_summary.cell(row=start_r2, column=col_idx, value=h)
        c.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    for r_idx, row in reason_df.iterrows():
        row_num = start_r2 + 1 + r_idx
        ws_summary.cell(row=row_num, column=1, value=row["rejection_reason"]).font = data_font
        ws_summary.cell(row=row_num, column=2, value=int(row["rejected_count"])).number_format = "#,##0"
        ws_summary.cell(row=row_num, column=3, value=float(row["pct_of_quarantine"]) / 100.0).number_format = "0.00%"
        ws_summary.cell(row=row_num, column=4, value=float(row["pct_of_raw"]) / 100.0).number_format = "0.000%"
        for c_idx in range(1, 5):
            ws_summary.cell(row=row_num, column=c_idx).border = thin_border

    # Auto-adjust column widths
    for col in ws_summary.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_summary.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # Sheet 2: Quarantined Records List
    ws_detail = wb.create_sheet(title="Quarantined_Records")
    headers_detail = list(sample_q_df.columns)
    for col_idx, h in enumerate(headers_detail, 1):
        c = ws_detail.cell(row=1, column=col_idx, value=h)
        c.fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    for r_idx, row in sample_q_df.iterrows():
        row_num = 2 + r_idx
        for c_idx, val in enumerate(row, 1):
            cell = ws_detail.cell(row=row_num, column=c_idx, value=str(val) if val is not None else "")
            cell.font = data_font
            cell.border = thin_border

    for col in ws_detail.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_detail.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    wb.save(reconciliation_xlsx)
    print(f"Workbook saved successfully to: {reconciliation_xlsx}", flush=True)
    print("=" * 70, flush=True)
    print("GATE 2 TRANSFORMATION COMPLETE", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_transformation()
