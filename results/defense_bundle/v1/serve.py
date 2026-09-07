from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import os,webbrowser
os.chdir(Path(__file__).parent)
server=None
for port in range(8765,8776):
    try:
        server=ThreadingHTTPServer(('127.0.0.1',port),SimpleHTTPRequestHandler);break
    except OSError:
        pass
if server is None: raise SystemExit('No free demo port from 8765 to 8775')
url='http://127.0.0.1:%d/'%server.server_port
webbrowser.open(url);print('Defense replay: '+url);server.serve_forever()
