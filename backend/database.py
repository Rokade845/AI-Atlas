import sqlite3
import os
import json

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Sectors table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sectors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        definition TEXT,
        key_companies TEXT,
        ai_adoption TEXT,
        market_size TEXT,
        regulatory_complexity TEXT,
        platform_priority TEXT,
        primary_entry_point TEXT
    );
    """)
    
    # 2. Companies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        country TEXT NOT NULL,
        ai_category TEXT,
        seg_tags TEXT, -- Comma-separated list of sector IDs
        germany_presence TEXT,
        company_type TEXT,
        use_cases TEXT,
        customers TEXT,
        funding TEXT,
        revenue TEXT,
        maturity TEXT,
        deployment_evidence TEXT,
        website TEXT,
        embedding TEXT -- JSON serialized float list for caching
    );
    """)
    
    # 3. Problems table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS problems (
        id TEXT PRIMARY KEY,
        category TEXT,
        statement TEXT NOT NULL,
        seg_tags TEXT, -- Comma-separated list of sector IDs, or 'ALL'
        vc_stage TEXT,
        severity INTEGER,
        use_case_solution TEXT,
        affected_companies TEXT,
        financial_impact TEXT,
        regulatory_trigger TEXT,
        problem_type TEXT,
        embedding TEXT
    );
    """)
    
    # 4. Problem-Company Mappings (ranked benchmarks)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS problem_company_mappings (
        id INTEGER PRIMARY KEY,
        problem_statement TEXT,
        seg_tags TEXT,
        vc_stage TEXT,
        ai_solution_1 TEXT,
        ai_solution_2 TEXT,
        ai_solution_3 TEXT,
        ranked_vendors TEXT,
        roi_benchmark TEXT,
        payback_months INTEGER,
        regulatory_benefit TEXT,
        embedding TEXT
    );
    """)
    
    # 5. News Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        headline TEXT NOT NULL,
        source TEXT,
        publication_date TEXT,
        summary TEXT,
        url TEXT UNIQUE,
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        embedding TEXT,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
    );
    """)
    
    # 6. Watchlist table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        company_id INTEGER PRIMARY KEY,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
    );
    """)
    
    conn.commit()
    conn.close()

# --- Companies CRUD ---

def get_companies(search=None, segment=None, company_type=None, maturity=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR ai_category LIKE ? OR use_cases LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    if company_type:
        query += " AND company_type = ?"
        params.append(company_type)
        
    if maturity:
        query += " AND maturity LIKE ?"
        params.append(f"%{maturity}%")
        
    companies = [dict(row) for row in cursor.execute(query, params).fetchall()]
    
    # Apply segment filtering programmatically since seg_tags is comma-separated
    if segment:
        filtered = []
        for c in companies:
            tags = [t.strip() for t in c['seg_tags'].split(',')] if c['seg_tags'] else []
            if str(segment) in tags:
                filtered.append(c)
        companies = filtered
        
    conn.close()
    return companies

def get_company(company_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    company_row = cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not company_row:
        conn.close()
        return None
        
    company = dict(company_row)
    
    # Fetch news
    news_rows = cursor.execute(
        "SELECT * FROM news_items WHERE company_id = ? ORDER BY publication_date DESC, id DESC",
        (company_id,)
    ).fetchall()
    company['news'] = [dict(row) for row in news_rows]
    
    # Fetch whether watchlisted
    watchlist_row = cursor.execute("SELECT 1 FROM watchlist WHERE company_id = ?", (company_id,)).fetchone()
    company['is_watched'] = watchlist_row is not None
    
    # Fetch solved problems
    # A company solves a problem if:
    # 1. The company's segment tags overlap with the problem's segment tags
    # 2. Or the company name is listed as a ranked vendor for a problem mapping
    company_segs = set([t.strip() for t in company['seg_tags'].split(',')]) if company['seg_tags'] else set()
    
    # Let's get all problems
    all_problems = cursor.execute("SELECT * FROM problems").fetchall()
    solved_problems = []
    for p in all_problems:
        p_segs_str = p['seg_tags']
        is_solved = False
        if p_segs_str == 'ALL':
            is_solved = True
        elif p_segs_str:
            p_segs = set([t.strip() for t in p_segs_str.split(',')])
            if company_segs & p_segs:
                is_solved = True
                
        # If it's a match, verify if there is an explicit mapping with ranked vendors
        if is_solved:
            p_dict = dict(p)
            # Find if there is an ROI mapping for this problem statement
            # We will search by matching problem statement substring
            mapping_row = cursor.execute(
                "SELECT * FROM problem_company_mappings WHERE problem_statement LIKE ? OR ? LIKE '%' || problem_statement || '%'",
                (f"%{p['statement']}%", p['statement'])
            ).fetchone()
            if mapping_row:
                m = dict(mapping_row)
                p_dict['roi_benchmark'] = m['roi_benchmark']
                p_dict['payback_months'] = m['payback_months']
                p_dict['regulatory_benefit'] = m['regulatory_benefit']
                p_dict['is_core_solution'] = company['name'].lower() in m['ranked_vendors'].lower()
            else:
                p_dict['is_core_solution'] = False
            
            solved_problems.append(p_dict)
            
    # Sort solved problems: core solutions first, then by severity descending
    solved_problems.sort(key=lambda x: (x.get('is_core_solution', False), x.get('severity', 0)), reverse=True)
    company['solved_problems'] = solved_problems
    
    conn.close()
    return company

def add_company(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO companies (
            name, country, ai_category, seg_tags, germany_presence,
            company_type, use_cases, customers, funding, revenue,
            maturity, deployment_evidence, website
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('name'),
            data.get('country'),
            data.get('ai_category'),
            data.get('seg_tags'),
            data.get('germany_presence'),
            data.get('company_type'),
            data.get('use_cases'),
            data.get('customers'),
            data.get('funding'),
            data.get('revenue'),
            data.get('maturity'),
            data.get('deployment_evidence'),
            data.get('website')
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError:
        # Handle deduplication
        existing = cursor.execute("SELECT id FROM companies WHERE name = ?", (data.get('name'),)).fetchone()
        if existing:
            return existing[0]
        raise
    finally:
        conn.close()

def update_company(company_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Construct update query dynamically
    fields = []
    params = []
    for k, v in data.items():
        if k in ['name', 'country', 'ai_category', 'seg_tags', 'germany_presence',
                 'company_type', 'use_cases', 'customers', 'funding', 'revenue',
                 'maturity', 'deployment_evidence', 'website', 'embedding']:
            fields.append(f"{k} = ?")
            params.append(v)
            
    if not fields:
        conn.close()
        return False
        
    params.append(company_id)
    cursor.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

# --- Sectors and Problems ---

def get_sectors():
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM sectors ORDER BY id ASC").fetchall()
    sectors = [dict(row) for row in rows]
    conn.close()
    return sectors

def get_problems():
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM problems ORDER BY id ASC").fetchall()
    problems = [dict(row) for row in rows]
    conn.close()
    return problems

# --- News CRUD ---

def add_news_item(company_id, headline, source, pub_date, summary, url):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO news_items (company_id, headline, source, publication_date, summary, url)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (company_id, headline, source, pub_date, summary, url))
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError:
        # Already exists
        return None
    finally:
        conn.close()

def get_all_news(limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT n.*, c.name as company_name 
        FROM news_items n
        JOIN companies c ON n.company_id = c.id
        ORDER BY n.publication_date DESC, n.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    news = [dict(row) for row in rows]
    conn.close()
    return news

# --- Watchlist CRUD ---

def toggle_watchlist(company_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    exists = cursor.execute("SELECT 1 FROM watchlist WHERE company_id = ?", (company_id,)).fetchone()
    if exists:
        cursor.execute("DELETE FROM watchlist WHERE company_id = ?", (company_id,))
        added = False
    else:
        cursor.execute("INSERT INTO watchlist (company_id) VALUES (?)", (company_id,))
        added = True
        
    conn.commit()
    conn.close()
    return added

def get_watchlist():
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT c.* 
        FROM watchlist w
        JOIN companies c ON w.company_id = c.id
        ORDER BY c.name ASC
    """).fetchall()
    companies = [dict(row) for row in rows]
    conn.close()
    return companies

# --- Embeddings Cache ---

def update_embedding(table_name, record_id, embedding_vector):
    conn = get_db_connection()
    cursor = conn.cursor()
    embedding_json = json.dumps(embedding_vector)
    
    if table_name == "companies":
        cursor.execute("UPDATE companies SET embedding = ? WHERE id = ?", (embedding_json, record_id))
    elif table_name == "problems":
        cursor.execute("UPDATE problems SET embedding = ? WHERE id = ?", (embedding_json, record_id))
    elif table_name == "problem_company_mappings":
        cursor.execute("UPDATE problem_company_mappings SET embedding = ? WHERE id = ?", (embedding_json, record_id))
    elif table_name == "news_items":
        cursor.execute("UPDATE news_items SET embedding = ? WHERE id = ?", (embedding_json, record_id))
        
    conn.commit()
    conn.close()

def get_all_embeddings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    embeddings = []
    
    # Fetch companies
    for row in cursor.execute("SELECT id, name, ai_category, use_cases, embedding FROM companies").fetchall():
        if row['embedding']:
            embeddings.append({
                'type': 'company',
                'id': row['id'],
                'name': row['name'],
                'text': f"Company: {row['name']}. AI Category: {row['ai_category']}. Use Cases: {row['use_cases']}",
                'vector': json.loads(row['embedding'])
            })
            
    # Fetch problems
    for row in cursor.execute("SELECT id, statement, use_case_solution, embedding FROM problems").fetchall():
        if row['embedding']:
            embeddings.append({
                'type': 'problem',
                'id': row['id'],
                'name': row['statement'],
                'text': f"Problem {row['id']}: {row['statement']}. AI Solution: {row['use_case_solution']}",
                'vector': json.loads(row['embedding'])
            })
            
    # Fetch mappings
    for row in cursor.execute("SELECT id, problem_statement, ranked_vendors, embedding FROM problem_company_mappings").fetchall():
        if row['embedding']:
            embeddings.append({
                'type': 'mapping',
                'id': row['id'],
                'name': row['problem_statement'],
                'text': f"Problem Mapping: {row['problem_statement']}. Ranked Vendors: {row['ranked_vendors']}",
                'vector': json.loads(row['embedding'])
            })
            
    # Fetch news
    for row in cursor.execute("SELECT n.id, n.headline, n.summary, c.name as company_name, n.embedding FROM news_items n JOIN companies c ON n.company_id = c.id").fetchall():
        if row['embedding']:
            embeddings.append({
                'type': 'news',
                'id': row['id'],
                'name': row['headline'],
                'text': f"News for {row['company_name']}: {row['headline']}. Summary: {row['summary']}",
                'vector': json.loads(row['embedding'])
            })
            
    conn.close()
    return embeddings
