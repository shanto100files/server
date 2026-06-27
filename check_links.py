import sqlite3, json

db = sqlite3.connect("cache.db")
cur = db.cursor()

# Check all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Check each table count
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cur.fetchone()[0]
    print(f"  {t}: {count} rows")

# Show sample scraped_content
print("\n--- scraped_content (sample 10) ---")
cur.execute("SELECT tmdb_id, title, media_type, scraped_at FROM scraped_content LIMIT 10")
for r in cur.fetchall():
    print(f"  tmdb={r[0]} | {r[1][:40]} | {r[2]}")

# Show sample content_cache
print("\n--- content_cache (sample 10) ---")
cur.execute("SELECT tmdb_id, title, media_type, year, rating, genres FROM content_cache LIMIT 10")
for r in cur.fetchall():
    print(f"  tmdb={r[0]} | {r[1][:40]} | {r[2]} | {r[3]} | rating={r[4]} | {r[5]}")

# Check if any provider stored links
print("\n--- Source cache (if any) ---")
try:
    cur.execute("SELECT key, provider, length(data) FROM source_cache LIMIT 10")
    for r in cur.fetchall():
        print(f"  {r[0][:50]} | {r[1]} | {r[2]} bytes")
except Exception as e:
    print(f"  Error: {e}")

db.close()
