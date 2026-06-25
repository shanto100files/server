import os, asyncio, sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from dotenv import load_dotenv
load_dotenv(r"E:\cinepix\termux-server\.env")

import redis.asyncio as aioredis

async def test():
    url = os.environ.get("REDIS_URL", "")
    print("URL: " + url[:35] + "...")
    
    r = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=5)
    
    try:
        await r.ping()
        print("Redis: CONNECTED")
    except Exception as e:
        print("Redis: FAIL - " + str(e)[:80])
        return
    
    # Write test
    t0 = time.time()
    for i in range(200):
        await r.setex("test:" + str(i), 3600, '{"sources": [{"url": "http://test.com"}]}')
    wt = (time.time() - t0) * 1000
    print("200 writes: {:.0f}ms ({:.1f}ms each)".format(wt, wt / 200))
    
    # Read test
    t0 = time.time()
    hits = 0
    for i in range(200):
        v = await r.get("test:" + str(i))
        if v: hits += 1
    rt = (time.time() - t0) * 1000
    print("200 reads:  {:.0f}ms ({:.1f}ms each) {}/200 hits".format(rt, rt / 200, hits))
    
    # Cleanup
    keys = []
    async for k in r.scan_iter("test:*"):
        keys.append(k)
    if keys:
        await r.delete(*keys)
    print("Cleanup: OK ({} keys)".format(len(keys)))
    
    # Memory
    info = await r.info("memory")
    print("Redis memory: {} MB".format(int(info.get("used_memory", 0)) / 1024 / 1024))
    
    await r.aclose()

asyncio.run(test())
