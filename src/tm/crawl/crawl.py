"""Crawler : visite la page d'accueil de chaque site et enregistre toutes les
requêtes réseau avec leur initiateur (CDP Network.requestWillBeSent), ce qui
permet de reconstruire les chaînes d'inclusion tiers -> tiers.

Installation : pip install -e . && python -m playwright install chromium

Usage :
  python -m tm.crawl.crawl --sites data/ref/sites_pilot.txt --out data/raw/crawl_pilot.jsonl

Quelques choix importants :
- l'isolation de sites de Chromium est désactivée, sinon les iframes d'un autre
  domaine tournent dans un autre processus et leurs requêtes nous échappent ;
- Debugger.enable est nécessaire pour avoir les piles d'appels JS ;
  setSkipAllPauses évite que les instructions `debugger;` des anti-bots bloquent ;
- un contexte navigateur neuf par site (sinon les cookies se mélangent) ;
- les valeurs des cookies ne sont pas enregistrées (vie privée) ;
- relancer la commande avec le même --out reprend là où le crawl s'est arrêté.
"""
import argparse
import asyncio
import json
import os
import re
import time

from playwright.async_api import async_playwright

CHALLENGE_TITLE = re.compile(
  r"(just a moment|attention required|checking your browser|verify you are human|"
  r"access denied|ddos-guard|security check|captcha)",
  re.I,
)
CHALLENGE_URL = re.compile(
  r"(challenges\.cloudflare\.com|/cdn-cgi/challenge-platform|ddos-guard\.net|hcaptcha\.com/captcha)")


def read_sites(path):
  """Lit une liste origine<TAB>palier<TAB>domaine (les 2 dernières colonnes sont optionnelles)."""
  sites = []
  with open(path, encoding="utf-8") as fh:
    for line in fh:
      line = line.strip()
      if not line or line.startswith("#"):
        continue
      parts = line.split("\t")
      origin = parts[0] if "://" in parts[0] else "https://" + parts[0]
      sites.append({"origin": origin,
                    "rank": parts[1] if len(parts) > 1 else None,
                    "site": parts[2] if len(parts) > 2 else None})
  return sites


def done_sites(path):
  """Origines déjà présentes dans le fichier de sortie (reprise du crawl)."""
  done = set()
  if os.path.exists(path):
    for line in open(path, encoding="utf-8"):
      try:
        done.add(json.loads(line)["origin"])
      except (json.JSONDecodeError, KeyError):
        pass
  return done


def stack_urls(stack, limit=12):
  """Aplatit la pile d'appels JS (y compris les piles async parentes)."""
  urls = []
  while stack and len(urls) < limit:
    for frame in stack.get("callFrames", []):
      if frame.get("url"):
        urls.append(frame["url"])
    stack = stack.get("parent")
  return urls[:limit]


async def visit(browser, item, args):
  t0 = time.time()
  rec = {"origin": item["origin"], "rank": item["rank"], "site": item["site"],
         "status": "ok", "error": None, "final_url": None, "title": None,
         "requests": [], "cookies": [], "ts": t0}
  seen_urls = {}        # requestId -> dernière URL vue, pour retrouver les redirections
  records = rec["requests"]
  context = await browser.new_context(
    user_agent=args.user_agent, locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh",
    ignore_https_errors=True, viewport={"width": 1366, "height": 768})
  try:
    page = await context.new_page()
    cdp = await context.new_cdp_session(page)

    def on_request(ev):
      r = ev["request"]
      ini = ev.get("initiator") or {}
      redirect_from = seen_urls.get(ev["requestId"]) if ev.get("redirectResponse") else None
      seen_urls[ev["requestId"]] = r["url"]
      records.append({
        "id": ev["requestId"], "url": r["url"], "method": r.get("method"),
        "type": ev.get("type"), "doc": ev.get("documentURL"), "frame": ev.get("frameId"),
        "init_type": ini.get("type"), "init_url": ini.get("url"),
        "stack": stack_urls(ini.get("stack")), "redirect_from": redirect_from,
        "t": round(ev.get("timestamp", 0), 3),
      })

    def on_paused(_):
      # Un `debugger;` a tout de même mis la page en pause : on la relance.
      asyncio.ensure_future(cdp.send("Debugger.resume"))

    cdp.on("Network.requestWillBeSent", on_request)
    cdp.on("Debugger.paused", on_paused)
    await cdp.send("Network.enable")
    await cdp.send("Debugger.enable")
    await cdp.send("Debugger.setSkipAllPauses", {"skip": True})
    await cdp.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 32})

    try:
      resp = await page.goto(item["origin"], wait_until="load", timeout=args.timeout * 1000)
      if resp is not None and resp.status >= 400:
        rec["status"] = "http_error"
        rec["error"] = f"HTTP {resp.status}"
    except Exception as e:                      # timeout ou erreur réseau
      msg = str(e).splitlines()[0][:300]
      rec["status"] = "timeout" if "Timeout" in msg else "error"
      rec["error"] = msg

    if rec["status"] in ("ok", "http_error", "timeout"):
      # Laisse les traceurs différés se déclencher, puis fait défiler la page.
      await page.wait_for_timeout(args.wait_after_load * 1000)
      try:
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(1500)
        rec["final_url"] = page.url
        rec["title"] = (await page.title())[:200]
      except Exception:
        pass

    if (rec["title"] and CHALLENGE_TITLE.search(rec["title"])) or \
        any(CHALLENGE_URL.search(r["url"]) for r in records):
      rec["challenge"] = True

    for c in await context.cookies():
      rec["cookies"].append({"domain": c.get("domain"), "name": c.get("name"),
                             "expires": c.get("expires"), "httpOnly": c.get("httpOnly"),
                             "sameSite": c.get("sameSite")})
  except Exception as e:
    rec["status"] = "error"
    rec["error"] = str(e).splitlines()[0][:300]
  finally:
    try:
      await context.close()
    except Exception:
      pass
  rec["duration_s"] = round(time.time() - t0, 2)
  return rec


async def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--sites", required=True)
  ap.add_argument("--out", required=True)
  ap.add_argument("--concurrency", type=int, default=4)
  ap.add_argument("--timeout", type=int, default=30, help="secondes pour l'événement load")
  ap.add_argument("--wait-after-load", type=int, default=6)
  ap.add_argument("--limit", type=int, default=0)
  ap.add_argument("--headful", action="store_true")
  ap.add_argument("--host-rules", default=None, help="tests : --host-resolver-rules de Chromium")
  args = ap.parse_args()

  os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
  sites = read_sites(args.sites)
  done = done_sites(args.out)
  todo = [s for s in sites if s["origin"] not in done]
  if args.limit:
    todo = todo[:args.limit]
  print(f"{len(sites)} sites, {len(done)} déjà faits, {len(todo)} à visiter")

  launch_args = ["--disable-site-isolation-trials",
                 "--disable-features=IsolateOrigins,site-per-process",
                 "--no-first-run", "--disable-dev-shm-usage"]
  if args.host_rules:
    launch_args.append(f"--host-resolver-rules={args.host_rules}")

  async with async_playwright() as p:
    browser = await p.chromium.launch(headless=not args.headful, args=launch_args)
    major = browser.version.split(".")[0]
    args.user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
    queue = asyncio.Queue()
    for s in todo:
      queue.put_nowait(s)
    lock = asyncio.Lock()
    n_done = 0

    async def worker():
      nonlocal n_done
      while not queue.empty():
        item = queue.get_nowait()
        try:
          # Garde-fou : un site qui ne rend jamais la main bloquerait tout le crawl.
          budget = args.timeout + args.wait_after_load + 40
          rec = await asyncio.wait_for(visit(browser, item, args), timeout=budget)
        except asyncio.TimeoutError:
          rec = {"origin": item["origin"], "rank": item["rank"], "site": item["site"],
                 "status": "error", "error": "trop long", "requests": [], "cookies": [],
                 "duration_s": None}
        async with lock:
          with open(args.out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
          n_done += 1
          print(f"[{n_done}/{len(todo)}] {rec['status']:<10} {len(rec['requests']):>4} req "
                f"{rec['duration_s']}s {item['origin']}", flush=True)

    await asyncio.gather(*[worker() for _ in range(args.concurrency)])
    await browser.close()


if __name__ == "__main__":
  asyncio.run(main())
