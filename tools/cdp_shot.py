#!/usr/bin/env python3
"""Screenshots of a local test Nextcloud with headless Chromium over --remote-debugging-pipe.

  cdp_shot.py BASE USER PASS OUTDIR name=path [name=path ...]
"""
import base64, json, os, subprocess, sys, tempfile, time

base, user, pw, out = sys.argv[1:5]
pages = [a.split("=", 1) for a in sys.argv[5:]]
ACTIONS = {}   # name -> JS run after the page settled
os.makedirs(out, exist_ok=True)
r_ours, w_chrome = os.pipe()      # chrome writes fd 4 -> we read
r_chrome, w_ours = os.pipe()      # we write -> chrome reads fd 3
prof = tempfile.mkdtemp()


def child():
    import fcntl
    a = fcntl.fcntl(r_chrome, fcntl.F_DUPFD, 10)   # out of the way of 3 and 4 first
    b = fcntl.fcntl(w_chrome, fcntl.F_DUPFD, 10)
    os.dup2(a, 3)
    os.dup2(b, 4)
    os.set_inheritable(3, True)
    os.set_inheritable(4, True)


p = subprocess.Popen(["chromium", "--headless=new", "--remote-debugging-pipe", "--user-data-dir=" + prof,
                      "--no-first-run", "--hide-scrollbars", "--window-size=1440,900", "--lang=en-US", "about:blank"],
                     preexec_fn=child, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.close(r_chrome); os.close(w_chrome)
rf = os.fdopen(r_ours, "rb", buffering=0)
buf = b""
mid = 0


def send(method, params=None, session=None):
    global mid
    mid += 1
    msg = {"id": mid, "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    os.write(w_ours, json.dumps(msg).encode() + b"\0")
    return recv(mid)


def recv(want):
    global buf
    while True:
        while b"\0" not in buf:
            chunk = rf.read(1 << 20)
            if not chunk:
                raise SystemExit("chromium closed the pipe")
            buf += chunk
        raw, buf = buf.split(b"\0", 1)
        m = json.loads(raw)
        if m.get("id") == want:
            if "error" in m:
                raise SystemExit("%s" % m["error"])
            return m.get("result", {})


tid = send("Target.createTarget", {"url": "about:blank"})["targetId"]
sid = send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
send("Page.enable", session=sid)
send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 2, "mobile": False}, sid)


def ev(js):
    return send("Runtime.evaluate", {"expression": js, "awaitPromise": True, "returnByValue": True}, sid).get("result", {}).get("value")


def go(url, settle):
    send("Page.navigate", {"url": url}, sid)
    for _ in range(60):
        time.sleep(0.5)
        if ev("document.readyState") == "complete":
            break
    time.sleep(settle)


go(base + "/login", 2)
ev("""(() => {
  const set = (el, v) => { const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    s.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
  set(document.querySelector('input[name=user]'), %s);
  set(document.querySelector('input[name=password]'), %s);
  document.querySelector('button[type=submit]').click(); return true; })()""" % (json.dumps(user), json.dumps(pw)))
time.sleep(4)
for name, path in pages:
    path, _, js = path.partition("|")
    go(base + path, 5)
    if js:
        print(" action:", ev(js))
        time.sleep(8)
    data = send("Page.captureScreenshot", {"format": "png"}, sid)["data"]
    open(os.path.join(out, name + ".png"), "wb").write(base64.b64decode(data))
    print(name, ev("document.title"))
p.terminate()
