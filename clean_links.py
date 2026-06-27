import sqlite3

db = sqlite3.connect("cache.db")
cur = db.cursor()

cur.execute("SELECT COUNT(*) FROM scraped_links")
before = cur.fetchone()[0]

# Delete intermediate links
SKIP_DOMAINS = [
    "%hubcloud.cx%", "%hubcloud.com%", "%hub.cloud%",
    "%gofile.io%", "%drivebot%", "%fastdlserver%",
    "%bit.ly%", "%whistle.lat%", "%noirspy%",
    "%hubdrive%", "%gdxshare%", "%gpdl2.hubcloud%",
    "%hub.latent.click%", "%hub.pyramid.surf%",
    "%gpdl2%", "%fast-dl.one%",
]

deleted = 0
for pat in SKIP_DOMAINS:
    cur.execute("DELETE FROM scraped_links WHERE url LIKE ?", (pat,))
    deleted += cur.rowcount

db.commit()

cur.execute("SELECT COUNT(*) FROM scraped_links")
after = cur.fetchone()[0]

print(f"Before: {before} links")
print(f"Deleted: {deleted} bad links")
print(f"After: {after} links")

# Show sample of good links
print("\n--- Sample good links ---")
cur.execute("""
    SELECT title, quality, provider, url
    FROM scraped_links
    ORDER BY RANDOM()
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0][:35]:<35} | {r[1]:<6} | {r[2]:<10} | {r[3][:65]}")

db.close()
