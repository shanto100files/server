import sqlite3, json, time, os

db_path = os.path.join(os.path.dirname(__file__), "cache.db")
if not os.path.exists(db_path):
    print("cache.db not found locally!")
    exit(0)

db = sqlite3.connect(db_path)
cur = db.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}\n")

# Main cache
if "cache" in tables:
    cur.execute("SELECT COUNT(*) FROM cache")
    total = cur.fetchone()[0]
    cur.execute("SELECT provider, COUNT(*) FROM cache GROUP BY provider")
    by_prov = dict(cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM cache WHERE created_at > ?", (time.time() - 3600,))
    recent = cur.fetchone()[0]
    print(f"=== Main Cache ===")
    print(f"Total: {total}")
    print(f"Last 1hr: {recent}")
    print(f"By Provider: {json.dumps(by_prov, indent=2)}\n")

# Link cache
if "link_cache" in tables:
    cur.execute("SELECT COUNT(*) FROM link_cache")
    total = cur.fetchone()[0]
    cur.execute("SELECT provider, COUNT(*) FROM link_cache GROUP BY provider")
    by_prov = dict(cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM link_cache WHERE created_at > ?", (time.time() - 3600,))
    recent = cur.fetchone()[0]
    print(f"=== Link Cache (Intermediate Links) ===")
    print(f"Total: {total}")
    print(f"Last 1hr: {recent}")
    print(f"By Provider: {json.dumps(by_prov, indent=2)}")

    # Show some sample entries
    cur.execute("SELECT key, links, provider, created_at FROM link_cache ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    if rows:
        print(f"\n--- Latest 5 entries ---")
        for key, links_json, provider, created_at in rows:
            age_min = round((time.time() - created_at) / 60, 1)
            links = json.loads(links_json)
            print(f"  {key} | provider={provider} | links={len(links)} | {age_min}min ago")
else:
    print("link_cache table does NOT exist yet!")
    print("It will be created when the server starts.")

db.close()
