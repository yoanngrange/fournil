"""Drive headless Chrome to check the UI (CLAUDE.md: check at 1440 px and 390 px).

    uv run --with websockets python scripts/browser.py URL WIDTH HEIGHT [steps…]

Steps run in order:
    --wait JS      wait until the expression is truthy (max 30 s)
    --js JS        evaluate (awaited) and print the result
    --mouse X,Y    move the mouse
    --sleep S      wait S seconds
    --shot FILE    save a screenshot
Console errors and uncaught exceptions are printed at the end.
"""

import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333


async def main():
    url, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    steps = sys.argv[4:]
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={tempfile.mkdtemp()}",
         "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                await asyncio.sleep(0.2)
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            n = 0
            pending, logs = {}, []

            async def reader():
                async for msg in ws:
                    m = json.loads(msg)
                    if "id" in m and m["id"] in pending:
                        pending.pop(m["id"]).set_result(m)
                    elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] in ("error", "warning"):
                        args = " ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])
                        logs.append(f"console.{m['params']['type']}: {args}")
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        logs.append("exception: " + (d.get("exception", {}).get("description") or d.get("text", "")))

            asyncio.create_task(reader())

            async def call(method, **params):
                nonlocal n
                n += 1
                fut = asyncio.get_event_loop().create_future()
                pending[n] = fut
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                return (await asyncio.wait_for(fut, 60)).get("result", {})

            await call("Runtime.enable")
            await call("Page.enable")
            await call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=w < 600)
            if w < 600:
                await call("Emulation.setTouchEmulationEnabled", enabled=True)
            await call("Page.navigate", url=url)
            for kind, arg in zip(steps[::2], steps[1::2]):
                if kind == "--wait":
                    for _ in range(150):
                        r = await call("Runtime.evaluate", expression=f"!!({arg})", returnByValue=True)
                        if r.get("result", {}).get("value"):
                            break
                        await asyncio.sleep(0.2)
                    else:
                        logs.append(f"timeout waiting for: {arg}")
                elif kind == "--js":
                    r = await call("Runtime.evaluate", expression=arg, awaitPromise=True, returnByValue=True)
                    val = r.get("result", {}).get("value")
                    if val is not None:
                        print("js:", json.dumps(val, ensure_ascii=False)[:2500])
                    if "exceptionDetails" in r:
                        logs.append("js error: " + r["exceptionDetails"].get("exception", {}).get("description", ""))
                elif kind == "--mouse":
                    x, y = (float(v) for v in arg.split(","))
                    await call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
                elif kind == "--sleep":
                    await asyncio.sleep(float(arg))
                elif kind == "--shot":
                    r = await call("Page.captureScreenshot", format="png")
                    with open(arg, "wb") as f:
                        f.write(base64.b64decode(r["data"]))
                    print("shot:", arg)
            for line in logs:
                print(line)
    finally:
        proc.terminate()
        proc.wait()


asyncio.run(main())
