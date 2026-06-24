import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'E:\\ottboxbd1\\termux-server')
import server
for r in server.app.routes:
    path = getattr(r, 'path', None)
    if path:
        print(path)
