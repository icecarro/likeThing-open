# -*- coding: utf-8 -*-
"""本地问卷服务：静态页 + 接收提交 + 存库 + 自动出报告。

用法：python scripts/server.py 8799
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).resolve().parent.parent
QDIR = BASE / "问卷"
OUT = BASE / "out"
INBOX = BASE / "inbox"
REC = BASE / "data" / "records"
for d in (OUT, INBOX, REC):
    d.mkdir(parents=True, exist_ok=True)
DB = REC / "db.md"

MAX_DAY = int(os.environ.get("MAX_DAY", "30"))          # 每天最多生成多少份
MAX_PHONE = int(os.environ.get("MAX_PHONE", "2"))       # 同一手机号每天最多几份
SEM = threading.Semaphore(2)                            # 同时最多 2 个生成任务
_phone_hits = {}
_day_state = {"date": "", "count": 0}
_sids = {}

_int = json.loads((BASE / "data" / "interests.json").read_text(encoding="utf-8"))
FIELD_NAME = {f["id"]: f["name"] for f in _int["fields"]}


CUSTOMERS = OUT / "customers"
CUSTOMERS.mkdir(parents=True, exist_ok=True)


def next_id(phone=""):
    """编号 = 完整手机号；同一号码重复提交加 -2。"""
    base = phone if len(phone) == 11 else time.strftime("%m%d%H%M")
    rid = base
    i = 2
    while (INBOX / f"{rid}.json").exists() or (CUSTOMERS / rid).exists():
        rid = f"{base}-{i}"
        i += 1
    return rid


def mask(phone):
    return phone[:3] + "****" + phone[-4:] if len(phone) == 11 else phone


def append_md(rid, phone, answers, status="已提交"):
    age = answers.get("P1", "")
    p4 = answers.get("P4", "") or "未填"
    email = answers.get("P7", "") or "—"
    raw = answers.get("Q34")
    if isinstance(raw, (str, int, float)):
        fields = [str(raw)]
    elif isinstance(raw, list):
        fields = [str(x) for x in raw]
    else:
        fields = []
    names = [FIELD_NAME.get(f, f) for f in fields]
    if not DB.exists():
        DB.write_text(
            "# 客户库\n\n"
            "| 时间 | 编号 | 手机 | 邮箱 | 生日 | 年龄档 | 深耕行业 | 状态 |\n"
            "|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    line = (f"| {datetime.now():%Y-%m-%d %H:%M} | {rid} | {mask(phone)} | {email} | {p4} | {age} | "
            f"{' / '.join(names)} | {status} |\n")
    with DB.open("a", encoding="utf-8") as f:
        f.write(line)


def generate(rid, path, email=""):
    env = dict(os.environ)
    outdir = CUSTOMERS / rid
    with SEM:
        try:
            subprocess.run([sys.executable, str(BASE / "scripts" / "generate.py"),
                            "--answers", str(path), "--id", rid,
                            "--out-dir", str(outdir), "--engine", "llm"],
                           cwd=str(BASE), env=env, timeout=600,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print("generate failed", rid, e)
        else:
            png = outdir / "report.png"
            html = outdir / "report.html"
            if html.exists() and (not png.exists() or png.stat().st_mtime < html.stat().st_mtime):
                subprocess.run([sys.executable, str(BASE / "scripts" / "render_only.py"), str(outdir)],
                               cwd=str(BASE), env=env, timeout=300,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[done] {rid}", flush=True)
            if email:
                try:
                    r = subprocess.run([sys.executable, str(BASE / "scripts" / "send_email.py"),
                                        "--id", rid, "--to", email],
                                       cwd=str(BASE), env=env, timeout=180,
                                       capture_output=True, text=True, encoding="utf-8", errors="replace")
                    print(f"[mail] {rid} -> {email}: {(r.stdout or '').strip()} {(r.stderr or '').strip()}", flush=True)
                except Exception as e:
                    print("email failed", rid, e, flush=True)


def log_event(msg):
    try:
        with (REC / "submit.log").open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{msg}\n")
    except Exception:
        pass


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(QDIR), **kw)

    def end_headers(self):
        if self.path.endswith(".html") or self.path == "/":
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/status":
            rid = (parse_qs(u.query).get("id") or [""])[0]
            rid = re.sub(r"[^0-9\-]", "", rid)
            base = CUSTOMERS / rid
            png = base / "report.png"
            pdf = base / "report.pdf"
            mob = base / "report_mobile.jpg"
            return self._json({"ok": True, "ready": png.exists(),
                               "mobile": f"/out/customers/{rid}/report_mobile.jpg" if mob.exists() else "",
                               "png": f"/out/customers/{rid}/report.png" if png.exists() else "",
                               "pdf": f"/out/customers/{rid}/report.pdf" if pdf.exists() else ""})
        if u.path == "/api/records":
            return self._json({"ok": True, "db": str(DB),
                               "text": DB.read_text(encoding="utf-8") if DB.exists() else ""})
        if u.path.startswith("/out/"):
            rel = u.path[len("/out/"):]
            p = (OUT / rel).resolve()
            if OUT.resolve() in p.parents and p.exists():
                data = p.read_bytes()
                ctype = {"png": "image/png", "pdf": "application/pdf",
                         "json": "application/json"}.get(p.suffix.lstrip("."), "application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json({"ok": False, "error": "not found"}, 404)
        if u.path == "/":
            self.path = "/index.html"
        if self.path.startswith("/index.html"):
            try:
                ip = self.headers.get("CF-Connecting-IP") or self.client_address[0]
                with (REC / "visits.log").open("a", encoding="utf-8") as f:
                    f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{ip}\t{self.headers.get('User-Agent','')[:120]}\n")
            except Exception:
                pass
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/submit":
            return self._json({"ok": False, "error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            phone = str(body.get("phone") or "").strip()
            answers = body.get("answers") or {}
            sid = str(body.get("sid") or "")[:40]
            if sid and sid in _sids:
                log_event(f"DUPLICATE sid={sid} -> {_sids[sid]}")
                return self._json({"ok": True, "id": _sids[sid], "dup": True})
            if not re.fullmatch(r"1\d{10}", phone):
                log_event(f"BAD_PHONE {phone[:4]}***")
                return self._json({"ok": False, "error": "手机号不对"}, 400)
            day = time.strftime("%Y%m%d")
            if _day_state["date"] != day:
                _day_state.update(date=day, count=0)
            if _day_state["count"] >= MAX_DAY:
                return self._json({"ok": False, "error": "今天的名额满了，请联系顾问"}, 429)
            entry = _phone_hits.get(phone)
            if entry and entry[0] == day and entry[1] >= MAX_PHONE:
                return self._json({"ok": False, "error": "这个手机号今天已经提交过了"}, 429)
            _phone_hits[phone] = (day, (entry[1] if entry and entry[0] == day else 0) + 1)
            _day_state["count"] += 1
            email = str(body.get("email") or "").strip()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                email = ""
            answers["P0"] = phone
            if email:
                answers["P7"] = email
            rid = next_id(phone)
            if sid:
                _sids[sid] = rid
            payload = dict(answers)
            payload["_meta"] = {"id": rid, "time": datetime.now().isoformat(timespec="seconds"),
                                "ua": self.headers.get("User-Agent", "")}
            path = INBOX / f"{rid}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                append_md(rid, phone, answers)
            except Exception as e:
                print("[db warn]", rid, e)
            threading.Thread(target=generate, args=(rid, path, email), daemon=True).start()
            log_event(f"SUBMIT {rid} {mask(phone)} email={email or '-'} keys={len(answers)}")
            print(f"[submit] {rid} {mask(phone)}")
            return self._json({"ok": True, "id": rid})
        except Exception as e:
            log_event(f"ERROR {type(e).__name__}: {e}")
            return self._json({"ok": False, "error": str(e)}, 500)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
    print(f"serving {QDIR} on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
