"""أدوات مشتركة للاختبارات: سيرفر فى فولدر مؤقت + مفتاح تراخيص للاختبار بس."""

import os
import sys
import tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "license_tool"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from server import licensing  # noqa: E402
from server.service import Service, AppError, SessionError  # noqa: E402
import license_core  # noqa: E402

TEST_KEY = Ed25519PrivateKey.generate()
licensing.PUBLIC_KEY_HEX = TEST_KEY.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
_shadow_dir = tempfile.mkdtemp()
os.environ["TM_SHADOW_PATH"] = os.path.join(_shadow_dir, "ls.bin")


def reset_shadow():
    try:
        os.remove(os.environ["TM_SHADOW_PATH"])
    except OSError:
        pass


def license_code(plan=3, users=5, start=None, machine=None):
    code, _exp, _serial = license_core.make_code(TEST_KEY, machine or licensing.machine_code(), plan, users,
                                                 start or date.today())
    return code


class Client:
    """بينادى الخدمة زى ما الواجهة بتعمل (بالاسم + token)."""

    def __init__(self, service, token=None):
        self.s = service
        self.token = token

    def __getattr__(self, name):
        return lambda **kw: self.s.call(name, kw, self.token)


def new_company(users=5, plan=3):
    """سيرفر جديد متفعّل وفيه شركة ← (الخدمة، عميل المدير)."""
    reset_shadow()
    svc = Service(tempfile.mkdtemp(), "test")
    anon = Client(svc)
    anon.activate(code=license_code(plan, users))
    res = anon.create_company(company_name="مصنع الاختبار", full_name="المدير", username="admin", password="1234")
    return svc, Client(svc, res["token"])


def login(svc, username, password):
    return Client(svc, Client(svc).login(username=username, password=password)["token"])
