"""
50-User Load Test — Random TMDB content, concurrent SSE streams
Measures: success rate, response time, timeout rate, provider stats
"""
import httpx
import asyncio
import time
import random
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TMDB_KEY = "2dca580c2a14b55200e8a6e860d7c9cf"
BASE = "http://localhost:8000"
NUM_USERS = 50
PROVIDER_TIMEOUT = 30  # seconds per provider
TOTAL_TIMEOUT = 90     # seconds per user max

# Popular movie and TV IDs for random testing
MOVIE_IDS = [
    550, 680, 27205, 155, 13, 680, 120, 278, 424, 244786,
    76341, 101, 597, 496243, 299536, 324857, 1726, 598, 24428,
    122, 299534, 429617, 11, 1891, 872585, 315162, 475557,
    346364, 438148, 245891, 419704, 508947, 569094, 453395,
    791373, 385687, 667538, 916967, 545609, 1022789, 575264,
    823464, 269149, 762441, 614696, 380975, 453395, 505703,
    974453, 1064028, 762504, 882598, 502356, 1197306, 929590,
]

TV_IDS = [
    1399, 94997, 1396, 60735, 66732, 71712, 93405, 60059,
    1398, 84958, 76479, 85937, 95557, 100088, 456, 114461,
    84773, 90462, 63174, 82856, 94997, 74577, 37854, 60735,
    90803, 44216, 92783, 71912, 87108, 4607, 99966, 124364,
    30984, 75556, 139510, 92685, 93743, 110316, 111191, 1399,
]

TMDB_TITLE_CACHE = {}


def get_title(tmdb_id, is_tv=False):
    cache_key = f"{'tv' if is_tv else 'movie'}:{tmdb_id}"
    if cache_key in TMDB_TITLE_CACHE:
        return TMDB_TITLE_CACHE[cache_key]
    try:
        r = httpx.get(
            f"https://api.themoviedb.org/3/{'tv' if is_tv else 'movie'}/{tmdb_id}",
            params={"api_key": TMDB_KEY},
            timeout=5,
        )
        data = r.json()
        title = data.get("title") or data.get("name") or f"Unknown {tmdb_id}"
        year = (data.get("release_date") or data.get("first_air_date") or "")[:4]
        TMDB_TITLE_CACHE[cache_key] = (title, year)
        return title, year
    except Exception:
        return f"Unknown {tmdb_id}", ""


async def single_user(user_id):
    """Simulate one user requesting random content"""
    is_tv = random.random() < 0.4  # 40% TV, 60% movie
    if is_tv:
        tmdb_id = str(random.choice(TV_IDS))
    else:
        tmdb_id = str(random.choice(MOVIE_IDS))

    title, year = get_title(tmdb_id, is_tv)
    media_type = "tv" if is_tv else "movie"
    season = random.randint(1, 5) if is_tv else 0
    episode = random.randint(1, 12) if is_tv else 0

    t0 = time.time()
    result = {
        "user_id": user_id,
        "tmdb_id": tmdb_id,
        "title": title,
        "year": year,
        "type": media_type,
        "season": season,
        "episode": episode,
        "status": "unknown",
        "sources": 0,
        "provider_times": {},
        "duration": 0,
        "error": None,
    }

    try:
        url = f"{BASE}/v1/movies/{tmdb_id}/sources/stream"
        params = {
            "type": media_type,
            "title": title,
            "season": season,
            "episode": episode,
            "year": year,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(TOTAL_TIMEOUT)) as client:
            async with client.stream("GET", url, params=params) as resp:
                if resp.status_code != 200:
                    result["status"] = f"http_{resp.status_code}"
                    result["duration"] = round(time.time() - t0, 2)
                    return result

                provider_count = 0
                source_count = 0
                provider_times = {}
                done = False

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") == "provider_done":
                        provider_count += 1
                        n = data.get("name", "?")
                        c = data.get("count", 0)
                        provider_times[n] = c
                        source_count += c

                    elif data.get("type") == "done":
                        total = data.get("total_sources", 0)
                        ptimes = data.get("provider_times", {})
                        result["sources"] = total
                        result["provider_times"] = ptimes
                        result["status"] = "success" if total > 0 else "no_sources"
                        done = True

                    elif data.get("type") == "error":
                        result["status"] = "error"
                        result["error"] = data.get("error", "unknown")
                        done = True

                if not done:
                    result["status"] = "timeout_no_done"

    except httpx.TimeoutException:
        result["status"] = "timeout"
    except httpx.ConnectError:
        result["status"] = "connect_error"
    except Exception as e:
        result["status"] = "exception"
        result["error"] = str(e)[:100]

    result["duration"] = round(time.time() - t0, 2)
    return result


async def main():
    print("=" * 70)
    print(f"  CinePix Load Test: {NUM_USERS} concurrent users")
    print(f"  Server: {BASE}")
    print(f"  Content: Random TMDB movies + TV shows")
    print("=" * 70)
    print()

    # Warm up title cache
    print("Warming up title cache...")
    warmup_ids = random.sample(MOVIE_IDS + TV_IDS, 20)
    for tid in warmup_ids:
        get_title(str(tid), random.random() < 0.4)
    print(f"  Cached {len(TMDB_TITLE_CACHE)} titles")
    print()

    print(f"Starting {NUM_USERS} concurrent users...")
    t_start = time.time()

    # Launch all users simultaneously
    tasks = [single_user(i) for i in range(NUM_USERS)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    t_total = round(time.time() - t_start, 2)

    # Analyze results
    successes = [r for r in results if isinstance(r, dict) and r["status"] == "success"]
    no_sources = [r for r in results if isinstance(r, dict) and r["status"] == "no_sources"]
    timeouts = [r for r in results if isinstance(r, dict) and r["status"] == "timeout"]
    errors = [r for r in results if isinstance(r, dict) and r["status"] not in ("success", "no_sources", "timeout")]

    all_results = [r for r in results if isinstance(r, dict)]

    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(f"  Total users:      {NUM_USERS}")
    print(f"  Success (>0 src): {len(successes)} ({len(successes)*100//NUM_USERS}%)")
    print(f"  No sources:       {len(no_sources)} ({len(no_sources)*100//NUM_USERS}%)")
    print(f"  Timeouts:         {len(timeouts)} ({len(timeouts)*100//NUM_USERS}%)")
    print(f"  Errors:           {len(errors)} ({len(errors)*100//NUM_USERS}%)")
    print(f"  Total time:       {t_total}s")
    print()

    if all_results:
        durations = [r["duration"] for r in all_results]
        source_counts = [r["sources"] for r in all_results]
        avg_dur = sum(durations) / len(durations)
        max_dur = max(durations)
        min_dur = min(durations)
        avg_src = sum(source_counts) / len(source_counts)

        print("  Timing:")
        print(f"    Avg duration:   {avg_dur:.1f}s")
        print(f"    Min duration:   {min_dur:.1f}s")
        print(f"    Max duration:   {max_dur:.1f}s")
        print()
        print("  Sources per user:")
        print(f"    Avg sources:    {avg_src:.1f}")
        print(f"    Max sources:    {max(source_counts)}")
        print(f"    Min sources:    {min(source_counts)}")
        print()

    # Provider stats
    all_ptimes = {}
    for r in all_results:
        for pname, pdur in r.get("provider_times", {}).items():
            if pname not in all_ptimes:
                all_ptimes[pname] = []
            all_ptimes[pname].append(pdur)

    if all_ptimes:
        print("  Provider Performance:")
        print(f"  {'Provider':<15} {'Avg(s)':<10} {'Min(s)':<10} {'Max(s)':<10} {'Hits':<10}")
        print("  " + "-" * 55)
        for pname, times in sorted(all_ptimes.items(), key=lambda x: -len(x[1])):
            avg_t = sum(times) / len(times)
            print(f"  {pname:<15} {avg_t:<10.1f} {min(times):<10.1f} {max(times):<10.1f} {len(times):<10}")
        print()

    # Source breakdown by content type
    movies = [r for r in all_results if r["type"] == "movie"]
    tvs = [r for r in all_results if r["type"] == "tv"]
    if movies:
        avg_mov = sum(r["sources"] for r in movies) / len(movies)
        print(f"  Movies: {len(movies)} users, avg {avg_mov:.1f} sources")
    if tvs:
        avg_tv = sum(r["sources"] for r in tvs) / len(tvs)
        print(f"  TV:     {len(tvs)} users, avg {avg_tv:.1f} sources")
    print()

    # Error details
    if errors:
        print("  Errors:")
        for e in errors[:10]:
            print(f"    User {e['user_id']}: {e['status']} - {e.get('error', 'N/A')[:60]}")
        if len(errors) > 10:
            print(f"    ... and {len(errors)-10} more")
        print()

    print("=" * 70)

    # Save results to file
    with open("loadtest_results.json", "w") as f:
        json.dump({
            "timestamp": time.time(),
            "num_users": NUM_USERS,
            "total_time": t_total,
            "results": [r for r in results if isinstance(r, dict)],
        }, f, indent=2, default=str)
    print("  Results saved to loadtest_results.json")


if __name__ == "__main__":
    asyncio.run(main())
