"""
api.py — السيرفر اللى الأجهزة التانية بتكلّمه على شبكة المحل
-----------------------------------------------------------
- POST /rpc   {"method": "...", "params": {...}}  + هيدر X-Token (بعد الدخول)
      ← {"ok": true, "result": ...}  أو  {"ok": false, "error": "رسالة عربى", "code": "error|session"}
- GET  /ping  ← {"app": "TailorMaster", ...}  (عشان الأجهزة تتأكد إنها لاقت السيرفر الصح)
- UDP 47811: الأجهزة بتدوّر على السيرفر لوحدها (زرار "دوّر على السيرفر").
- كل يوم: نسخة احتياطية أوتوماتيك فى فولدر backups.
"""

import json
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .service import AppError

DEFAULT_PORT = 47810
DISCOVERY_PORT = 47811
DISCOVERY_ASK = b"TAILORMASTER_DISCOVER"
MAX_BODY_MB = 40


def _make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TailorMaster"
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):      # من غير كلام فى الشاشة مع كل طلب
            pass

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip("/") == "/ping":
                try:
                    st = service.call("status")
                except Exception:  # noqa: BLE001
                    st = {}
                self._send(200, {"app": "TailorMaster", "version": service.app_version,
                                 "company": st.get("company")})
            else:
                self._send(404, {"ok": False, "error": "مش موجود"})

        def do_POST(self):
            if self.path.rstrip("/") != "/rpc":
                self._send(404, {"ok": False, "error": "مش موجود"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY_MB * 1024 * 1024:
                self._send(413, {"ok": False, "error": f"الطلب كبير أوى (أقصى حاجة {MAX_BODY_MB} ميجا)"})
                return
            try:
                req = json.loads(self.rfile.read(length).decode("utf-8"))
                method, params = req.get("method"), req.get("params") or {}
                if not isinstance(params, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError, AttributeError):
                self._send(400, {"ok": False, "error": "طلب غير مفهوم"})
                return
            try:
                result = service.call(method, params, self.headers.get("X-Token"))
                self._send(200, {"ok": True, "result": result})
            except AppError as e:
                self._send(200, {"ok": False, "error": str(e), "code": e.code})
            except Exception as e:  # noqa: BLE001 - أى خطأ مش متوقع يرجع رسالة بدل ما السيرفر يقع
                traceback.print_exc()
                self._send(200, {"ok": False, "error": f"حصل خطأ فى السيرفر: {e}", "code": "error"})

    return Handler


class ApiServer:
    def __init__(self, service, host="0.0.0.0", port=DEFAULT_PORT):
        self.service = service
        self.host = host
        self.port = port
        self._httpd = None
        self._udp = None
        self._stop = threading.Event()

    def start(self):
        """بيرمى OSError لو البورت مشغول (يعنى غالبًا السيرفر شغّال بالفعل)."""
        self._httpd = ThreadingHTTPServer((self.host, self.port), _make_handler(self.service))
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self.service.port = self.port
        threading.Thread(target=self._httpd.serve_forever, daemon=True, name="api").start()
        threading.Thread(target=self._discovery_loop, daemon=True, name="discovery").start()
        threading.Thread(target=self._backup_loop, daemon=True, name="backup").start()
        return self.port

    def stop(self):
        self._stop.set()
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._udp:
            try:
                self._udp.close()
            except OSError:
                pass

    def _discovery_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(1.0)
        except OSError:
            return              # البحث الأوتوماتيك مش هيشتغل، بس الكتابة بالـ IP لسه شغالة
        self._udp = sock
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(256)
            except socket.timeout:
                continue
            except OSError:
                return
            if data.strip() == DISCOVERY_ASK:
                try:
                    company = self.service.call("status").get("company")
                except Exception:  # noqa: BLE001
                    company = None
                reply = json.dumps({"app": "TailorMaster", "port": self.port, "company": company},
                                   ensure_ascii=False).encode()
                try:
                    sock.sendto(reply, addr)
                except OSError:
                    pass

    def _backup_loop(self):
        while not self._stop.is_set():
            try:
                self.service.auto_backup()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            self._stop.wait(3600)          # بيتأكد كل ساعة؛ النسخة بتتعمل مرة واحدة فى اليوم


# ========================= أدوات الشبكة (للواجهة كمان) =========================

def local_ips():
    """عناوين الجهاز ده على الشبكة (عشان المدير يديها للموظفين)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))        # مش بيبعت حاجة فعلاً
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")] or ["127.0.0.1"]


def discover(timeout=1.5):
    """بيدوّر على سيرفرات البرنامج على الشبكة ← [(ip, port, اسم الشركة)]."""
    found = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)
        for target in ("255.255.255.255", "<broadcast>"):
            try:
                sock.sendto(DISCOVERY_ASK, (target, DISCOVERY_PORT))
            except OSError:
                pass
        import time
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                info = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            if info.get("app") == "TailorMaster":
                found[addr[0]] = (addr[0], int(info.get("port") or DEFAULT_PORT), info.get("company"))
        sock.close()
    except OSError:
        pass
    return list(found.values())
