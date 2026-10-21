"""
qt_worker.py
------------
بيشغّل أى كلام مع السيرفر فى thread منفصل عشان الواجهة متهنجش.

- الطلبات بتتنفذ واحدة ورا التانية (لو حد داس على زرار مرتين، التانية
  بتلاقى الحالة اتغيرت فبترفض).
- Qt مينفعش تتلمس غير من الـ main thread، فالنتيجة بتتحط فى طابور
  و QTimer بيسحبها كل 50 ملّى ثانية وينادى الدالة المناسبة فى الواجهة.
- لو السيرفر قال "الجلسة خلصت": بدل رسالة الخطأ، البرنامج بيرجع لشاشة الدخول.
"""

import queue
import threading

from PySide6.QtCore import QTimer

from models import SessionExpired


class QtWorker:
    def __init__(self, on_unhandled_error):
        self._tasks = queue.Queue()
        self._results = queue.Queue()
        self._pending = 0
        self._busy_listeners = []
        self._on_unhandled_error = on_unhandled_error
        self.on_session_expired = None
        threading.Thread(target=self._loop, daemon=True).start()
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(50)

    def run(self, func, on_success=None, on_error=None):
        """func بتتنفذ فى الخلفية. on_success(result) / on_error(exception) فى الواجهة."""
        self._pending += 1
        self._notify()
        self._tasks.put((func, on_success, on_error))

    def is_busy(self) -> bool:
        return self._pending > 0

    def add_busy_listener(self, callback, owner=None):
        """owner = الشاشة صاحبة المؤشر (بيتشال لما الشاشة تتغير)."""
        self._busy_listeners.append((owner, callback))
        callback(self._pending > 0)

    def clear_busy_listeners(self, keep=None):
        """بيشيل مؤشرات الشاشات القديمة. keep = الشاشة الجديدة: مؤشرها بيفضل حتى لو اتسجل
        قبل ما تتعرض (وإلا "جارى التحميل" كانت بتفضل ظاهرة على طول)."""
        self._busy_listeners = [(o, c) for o, c in self._busy_listeners if keep is not None and o is keep]

    # ---------- داخلى ----------

    def _loop(self):
        while True:
            func, on_success, on_error = self._tasks.get()
            try:
                self._results.put((on_success, on_error, func(), None))
            except Exception as e:  # noqa: BLE001 - أى خطأ بيرجع للواجهة تعرضه
                self._results.put((on_success, on_error, None, e))

    def _poll(self):
        while True:
            try:
                on_success, on_error, result, error = self._results.get_nowait()
            except queue.Empty:
                return
            self._pending -= 1
            self._notify()
            try:
                if isinstance(error, SessionExpired) and self.on_session_expired:
                    self.on_session_expired(error)
                elif error is not None:
                    (on_error or self._on_unhandled_error)(error)
                elif on_success:
                    on_success(result)
            except RuntimeError as e:
                # الشاشة اللى كانت مستنية النتيجة اتقفلت (مثلاً عمل خروج) - Qt بيرمى
                # "Internal C++ object already deleted"، ومفيش حاجة نعملها
                if "deleted" not in str(e):
                    self._on_unhandled_error(e)
            except Exception as e:  # noqa: BLE001
                self._on_unhandled_error(e)

    def _notify(self):
        for _owner, callback in list(self._busy_listeners):
            try:
                callback(self._pending > 0)
            except RuntimeError:
                pass
