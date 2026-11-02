#!/usr/bin/env python3
import asyncio, json, sys, urllib.request, websockets

CDP_HTTP = "http://127.0.0.1:9222"

def get_ws_url():
    with urllib.request.urlopen(CDP_HTTP + "/json") as r:
        targets = json.load(r)
    for t in targets:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("No page target. Is Sonik running?")

async def send(ws, method, params, msg_id):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp

async def main():
    if len(sys.argv) < 2:
        print("Usage: sonik.py goto <url> | title | eval <js>")
        return
    sub = sys.argv[1]
    ws_url = get_ws_url()
    async with websockets.connect(ws_url) as ws:
        if sub == "goto":
            url = sys.argv[2]
            if not url.startswith("http"): url = "https://" + url
            r = await send(ws, "Page.navigate", {"url": url}, 1)
            print(json.dumps(r.get("result", r.get("error")), indent=2))
        elif sub == "title":
            r = await send(ws, "Runtime.evaluate",
                           {"expression": "document.title", "returnByValue": True}, 2)
            print(r["result"]["result"].get("value"))
        elif sub == "eval":
            js = " ".join(sys.argv[2:])
            r = await send(ws, "Runtime.evaluate",
                           {"expression": js, "returnByValue": True}, 3)
            print(r["result"]["result"].get("value"))

asyncio.run(main())
