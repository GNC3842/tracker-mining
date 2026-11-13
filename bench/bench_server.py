"""Banc de test local : simule des sites et des tiers sur des domaines fictifs
(résolus vers 127.0.0.1 par --host-resolver-rules) pour vérifier que le crawler
+ l'analyseur reconstruisent correctement les chaînes d'inclusion.

Vérité terrain (profondeur tierce minimale attendue pour news-bench.vn) :
  tagmgr-bench.com      1  (balise <script> dans le HTML)
  pixel-bench.org       1  (<img> direct dans le HTML ; aussi appelé à prof. 2)
  embed-bench.vn        1  (<iframe> dans le HTML)
  analytics-bench.net   2  (injecté dynamiquement par tagmgr, via setTimeout)
  deep-bench.net        2  (<script> dans l'iframe embed)
  ads-bench.io          3  (fetch() émis par analytics)
  deep-collect-bench.com 3 (fetch() émis par deep)
  cdn-bench.co          4  (redirection 302 depuis ads-bench.io/r)
"""
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
       b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")

def routes(port: int) -> dict:
    P = f":{port}"
    return {
        ("news-bench.vn", "/"): ("text/html", f"""<!doctype html><html><head><title>Báo Bench</title>
    <link rel="stylesheet" href="/style.css">
    <script src="http://tagmgr-bench.com{P}/gtm.js"></script></head>
    <body><h1>Tin tức</h1><img src="http://pixel-bench.org{P}/direct.gif">
    <iframe src="http://embed-bench.vn{P}/frame.html"></iframe></body></html>"""),
        ("news-bench.vn", "/style.css"): ("text/css", "body{{font-family:sans-serif}}"),
        ("tagmgr-bench.com", "/gtm.js"): ("application/javascript", f"""
    setTimeout(function(){{
      var s=document.createElement('script');
      s.src='http://analytics-bench.net{P}/a.js';
      document.head.appendChild(s);
    }}, 300);"""),
        ("analytics-bench.net", "/a.js"): ("application/javascript", f"""
    debugger;  // doit être ignoré grâce à Debugger.setSkipAllPauses
    fetch('http://ads-bench.io{P}/collect?uid=123', {{mode:'no-cors'}});
    new Image().src='http://pixel-bench.org{P}/p.gif?cid=42';
    fetch('http://ads-bench.io{P}/r', {{mode:'no-cors'}});"""),
        ("ads-bench.io", "/collect"): ("text/plain", "ok"),
        ("cdn-bench.co", "/x.gif"): ("image/gif", GIF),
        ("pixel-bench.org", "/direct.gif"): ("image/gif", GIF),
        ("pixel-bench.org", "/p.gif"): ("image/gif", GIF),
        ("embed-bench.vn", "/frame.html"): ("text/html", f"""<!doctype html><html><body>
    <script src="http://deep-bench.net{P}/d.js"></script></body></html>"""),
        ("deep-bench.net", "/d.js"): ("application/javascript",
                                      f"fetch('http://deep-collect-bench.com{P}/c', {{mode:'no-cors'}});"),
        ("deep-collect-bench.com", "/c"): ("text/plain", "ok"),
        ("cf-bench.vn", "/"): ("text/html", "<html><head><title>Just a moment...</title></head><body>…</body></html>"),
    }


def make_handler(port: int):
    table = routes(port)
    P = f":{port}"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            path = self.path.split("?")[0]
            if host == "ads-bench.io" and path == "/r":
                self.send_response(302)
                self.send_header("Location", f"http://cdn-bench.co{P}/x.gif")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            if host == "slow-bench.vn":
                time.sleep(25)
            ctype, body = table.get((host, path), ("text/plain", None))
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype or "javascript" in ctype else ""))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


    return H


def make_server(port: int = 0) -> ThreadingHTTPServer:
    """port=0 : port libre choisi par l'OS (tests). Le port réel est server.server_port,
    mais les routes doivent le connaître : on lie d'abord, puis on installe le handler."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    srv.RequestHandlerClass = make_handler(srv.server_port)
    return srv


if __name__ == "__main__":
    make_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8765).serve_forever()
