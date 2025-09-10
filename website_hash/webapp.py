# app_sqlite.py
import os
import sqlite3
from flask import Flask, jsonify, request, render_template, abort, g

app = Flask(__name__)

# -------------------------------------------------
# Configuration
# -------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
COLUMNS = ["name", "version", "sha256", "file", "url"]
TABLE   = "files"
DEFAULT_LIMIT = 50          # rows per page (adjust as you like)

# -------------------------------------------------
# SQLite connection handling (per‑request)
# -------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row   # dict‑like access
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# -------------------------------------------------
# Helper: build WHERE clause for free‑text search
# -------------------------------------------------
def build_search_clause(term: str):
    """Return (sql, params) that matches term in ANY column (case‑insensitive)."""
    if not term:
        return "", ()
    term_like = f"%{term.lower()}%"
    conditions = [f"LOWER({col}) LIKE ?" for col in COLUMNS]
    sql = "WHERE " + " OR ".join(conditions)
    params = tuple(term_like for _ in COLUMNS)
    return sql, params

# -------------------------------------------------
# API: /api/search
# -------------------------------------------------
@app.route("/api/search")
def api_search():
    """
    Query parameters
    ----------------
    q        : free‑text term (optional)
    sort_by  : column name (default: name)
    order    : asc|desc (default: asc)
    page     : 1‑based page number (default: 1)
    limit    : rows per page (default: 50)
    """
    q       = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort_by", "name")
    order   = request.args.get("order", "asc").lower()
    page    = max(int(request.args.get("page", 1)), 1)
    limit   = max(int(request.args.get("limit", DEFAULT_LIMIT)), 1)

    if sort_by not in COLUMNS:
        abort(400, description=f"Invalid sort_by column. Choose from {COLUMNS}")
    if order not in ("asc", "desc"):
        abort(400, description="order must be 'asc' or 'desc'")

    offset = (page - 1) * limit

    where_sql, where_params = build_search_clause(q)

    # Main query – fetch only the slice we need
    sql = f"""
        SELECT {', '.join(COLUMNS)}
        FROM {TABLE}
        {where_sql}
        ORDER BY {sort_by} {order.upper()}
        LIMIT ? OFFSET ?
    """
    params = (*where_params, limit, offset)

    db = get_db()
    rows = db.execute(sql, params).fetchall()

    # Optional: total count for UI pagination
    count_sql = f"SELECT COUNT(*) FROM {TABLE} {where_sql}"
    total = db.execute(count_sql, where_params).fetchone()[0]

    # Convert sqlite.Row objects to plain dicts
    data = [dict(row) for row in rows]

    return jsonify({
        "page": page,
        "limit": limit,
        "total": total,
        "results": data
    })

# -------------------------------------------------
# UI – unchanged (still uses index.html)
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", columns=COLUMNS)

# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
