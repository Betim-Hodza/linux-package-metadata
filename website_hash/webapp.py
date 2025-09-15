# app_multi_sqlite.py
import os, sqlite3
from flask import Flask, jsonify, request, render_template, g, abort

app = Flask(__name__)

# -----------------------------------------------------------------
# Configuration – list every CSV‑derived DB you want to expose
# -----------------------------------------------------------------
DB_FILES = {
    "data1": "data1.db",
    # "data2": "data2.db",
    # add more: "name": "filename.db"
}
COLUMNS = ["name", "version", "sha256", "file", "url"]
TABLE   = "files"
DEFAULT_LIMIT = 50

# -----------------------------------------------------------------
# Helper – open a connection and ATTACH all DBs once per request
# -----------------------------------------------------------------
def get_conn():
    if "conn" not in g:
        conn = sqlite3.connect(":memory:")          # in‑memory master DB
        conn.row_factory = sqlite3.Row
        # Attach each physical DB under its own schema name
        for alias, path in DB_FILES.items():
            conn.execute(f"ATTACH DATABASE '{os.path.abspath(path)}' AS {alias}")
        g.conn = conn
    return g.conn

@app.teardown_appcontext
def close_conn(exc):
    conn = g.pop("conn", None)
    if conn:
        conn.close()

# -----------------------------------------------------------------
# Build WHERE clause (same as before)
# -----------------------------------------------------------------
def build_search_clause(term):
    if not term:
        return "", ()
    term_like = f"%{term.lower()}%"
    cond = " OR ".join([f"LOWER({c}) LIKE ?" for c in COLUMNS])
    return f"WHERE {cond}", tuple(term_like for _ in COLUMNS)

# -----------------------------------------------------------------
# API – now you can query any attached DB via a `source` param
# -----------------------------------------------------------------
@app.route("/api/search")
def api_search():
    q       = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort_by", "name")
    order   = request.args.get("order", "asc").lower()
    page    = max(int(request.args.get("page", 1)), 1)
    limit   = max(int(request.args.get("limit", DEFAULT_LIMIT)), 1)
    source  = request.args.get("source", "data1")   # default DB

    if source not in DB_FILES:
        abort(400, f"Unknown source – choose from {list(DB_FILES)}")
    if sort_by not in COLUMNS:
        abort(400, f"Invalid sort_by – choose from {COLUMNS}")
    if order not in ("asc", "desc"):
        abort(400, "order must be asc or desc")

    offset = (page - 1) * limit
    where_sql, where_params = build_search_clause(q)

    sql = f"""
        SELECT {', '.join(COLUMNS)}
        FROM {source}.{TABLE}
        {where_sql}
        ORDER BY {sort_by} {order.upper()}
        LIMIT ? OFFSET ?
    """
    params = (*where_params, limit, offset)

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM {source}.{TABLE} {where_sql}", where_params
    ).fetchone()[0]

    return jsonify({
        "source": source,
        "page": page,
        "limit": limit,
        "total": total,
        "results": [dict(r) for r in rows]
    })

@app.route("/")
def index():
    return render_template("index.html", columns=COLUMNS, sources=list(DB_FILES))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
