import os
import csv
import sqlite3
from database import init_db, get_db_connection

def ingest_sectors(cursor, csv_path):
    print("Ingesting sectors...")
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
            INSERT OR REPLACE INTO sectors (
                id, name, definition, key_companies, ai_adoption,
                market_size, regulatory_complexity, platform_priority, primary_entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['Seg No.']),
                row['Segment Name'].strip(),
                row['Definition'].strip(),
                row['Key Germany Companies'].strip(),
                row['AI Adoption'].strip(),
                row['DE Market Size'].strip(),
                row['Regulatory Complexity'].strip(),
                row['Platform Priority'].strip(),
                row['Primary AI Entry Point'].strip()
            ))

def ingest_companies(cursor, csv_path):
    print("Ingesting companies...")
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
            INSERT OR REPLACE INTO companies (
                id, name, country, ai_category, seg_tags, germany_presence,
                company_type, use_cases, customers, funding, revenue,
                maturity, deployment_evidence, website
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['#']) if row['#'] else None,
                row['Vendor Name'].strip(),
                row['Country'].strip(),
                row['AI Category'].strip(),
                row['Seg Tags'].strip(),
                row['Germany Presence'].strip(),
                row['Company Type'].strip(),
                row['F&B AI Use Case'].strip(),
                row['Top Germany F&B Customers'].strip(),
                row['Funding'].strip(),
                row['Est. Revenue'].strip(),
                row['Maturity'].strip(),
                row['Top Deployment Evidence'].strip(),
                row['Website'].strip()
            ))

def ingest_problems(cursor, csv_path):
    print("Ingesting problems...")
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
            INSERT OR REPLACE INTO problems (
                id, category, statement, seg_tags, vc_stage, severity,
                use_case_solution, affected_companies, financial_impact, regulatory_trigger, problem_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['Prob ID'].strip(),
                row['Category'].strip(),
                row['Problem Statement'].strip(),
                row['Seg Tags'].strip(),
                row['VC Stage'].strip(),
                int(row['Severity']) if row['Severity'] else 0,
                row['AI Use Case Solution'].strip(),
                row['Affected Germany Companies'].strip(),
                row['Financial Impact (€)'].strip(),
                row['Regulatory Trigger'].strip(),
                row['Problem Type'].strip()
            ))

def ingest_mappings(cursor, csv_path):
    print("Ingesting problem-company mappings...")
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
            INSERT OR REPLACE INTO problem_company_mappings (
                id, problem_statement, seg_tags, vc_stage, ai_solution_1,
                ai_solution_2, ai_solution_3, ranked_vendors, roi_benchmark,
                payback_months, regulatory_benefit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['#']),
                row['Problem Statement'].strip(),
                row['Seg Tags'].strip(),
                row['VC Stage'].strip(),
                row['AI Solution 1'].strip(),
                row['AI Solution 2'].strip(),
                row['AI Solution 3'].strip(),
                row['Germany Vendors (ranked)'].strip(),
                row['ROI Benchmark'].strip(),
                int(row['Payback (months)']) if row['Payback (months)'] else 0,
                row['Regulatory Benefit'].strip()
            ))

def main():
    # Make sure DB schema is initialized
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    dataset_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "atlas_dataset")
    
    ingest_sectors(cursor, os.path.join(dataset_dir, "sectors_reference.csv"))
    ingest_companies(cursor, os.path.join(dataset_dir, "companies_germany.csv"))
    ingest_problems(cursor, os.path.join(dataset_dir, "problems_germany.csv"))
    ingest_mappings(cursor, os.path.join(dataset_dir, "problem_company_mapping.csv"))
    
    conn.commit()
    conn.close()
    print("Database ingestion completed successfully!")

if __name__ == "__main__":
    main()
