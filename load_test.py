import asyncio
from curl_cffi.requests import AsyncSession
import time
import os

# 50 unique movies with different TMDB IDs
MOVIES = [
    ("The Dark Knight", "155"),
    ("Pulp Fiction", "680"),
    ("Fight Club", "550"),
    ("Forrest Gump", "13"),
    ("The Matrix", "603"),
    ("Goodfellas", "769"),
    ("The Silence of the Lambs", "274"),
    ("Schindler's List", "424"),
    ("The Lord of the Rings", "120"),
    ("The Godfather", "238"),
    ("Shawshank Redemption", "278"),
    ("Gladiator", "98"),
    ("Braveheart", "197"),
    ("Saving Private Ryan", "857"),
    ("The Lion King", "8587"),
    ("Jurassic Park", "329"),
    ("Terminator 2", "280"),
    ("Die Hard", "562"),
    ("Back to the Future", "105"),
    ("Raiders of the Lost Ark", "85"),
    ("Alien", "348"),
    ("Predator", "106"),
    ("RoboCop", "5786"),
    ("Total Recall", "861"),
    ("The Truman Show", "37165"),
    ("American History X", "73"),
    ("Requiem for a Dream", "641"),
    ("Memento", "77"),
    ("Black Swan", "45612"),
    ("Whiplash", "244786"),
    ("La La Land", "313369"),
    ("Parasite", "496243"),
    ("Knives Out", "546554"),
    ("Get Out", "419430"),
    ("Us", "458156"),
    ("Hereditary", "493922"),
    ("Midsommar", "530385"),
    ("The Witch", "312221"),
    ("It", "346364"),
    ("Doctor Strange", "284052"),
    ("Black Panther", "284054"),
    ("Thor Ragnarok", "284053"),
    ("Guardians of the Galaxy", "118340"),
    ("Ant-Man", "102899"),
    ("Captain America Civil War", "271110"),
    ("Logan", "263115"),
    ("Deadpool", "293660"),
    ("Venom", "335983"),
    ("Aquaman", "297802"),
    ("Shazam", "287947"),
]

async def fetch_movie(session, user_id, title, tmdb_id):
    url = f"http://127.0.0.1:8000/v1/movies/{tmdb_id}/sources?title={title}&type=movie"
    start_time = time.time()
    try:
        response = await session.get(url, timeout=120)
        data = response.json()
        duration = time.time() - start_time
        sources = data.get("sources", [])
        status = "[OK]" if sources else "[NO SOURCES]"
        print(f"{status} [User {user_id:02d}] '{title}' -> {len(sources)} sources | {duration:.2f}s")
        return duration, len(sources)
    except Exception as e:
        duration = time.time() - start_time
        print(f"[ERR] [User {user_id:02d}] '{title}' -> ERROR: {str(e)[:60]} | {duration:.2f}s")
        return duration, 0

async def main():
    print("===================================================")
    print("  REAL LOAD TEST - 50 Unique Movies, No Cache")
    print("===================================================")
    start_time = time.time()

    async with AsyncSession() as session:
        tasks = []
        for i, (title, tmdb_id) in enumerate(MOVIES):
            tasks.append(fetch_movie(session, i + 1, title, tmdb_id))

        results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    successful = [r for r in results if r[1] > 0]
    total_sources = sum(r[1] for r in results)
    avg_duration = sum(r[0] for r in results) / len(results)

    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"Unique Movies Tested    : 50")
    print(f"Successful (Got Sources): {len(successful)}/50")
    print(f"Total Sources Found     : {total_sources}")
    print(f"Average Response Time   : {avg_duration:.2f}s")
    print(f"Total Wall Time         : {total_time:.2f}s")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
