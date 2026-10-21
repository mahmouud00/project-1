"""
qt_worker.py
------------
بيشغّل أي شغل مع جوجل في thread منفصل عشان الواجهة متهنجش.

- الطلبات بتتنفذ واحدة ورا التانية (مفيش عمليتين بيكتبوا في الشيت مع بعض،
  ولو حد داس على زرار مرتين، التانية بتلاقي الحالة اتغيرت فبترفض).
- Qt (زي Tkinter) مينفعش تتلمس غير من الـ main thread، فالنتيجة بتتحط في طابور
  و QTimer بيسحبها كل 50 ملّي ثانية وينادي الدالة المناسبة في الواجهة.
"""

import queue
import threading

from PySide6.QtCore import QTimer


class QtWorker:
    def __init__(self, on_unhandled_error):
        self._tasks = queue.Queue()
        self._results = queue.Queue()
        self._pending = 0
        self._busy_listeners = []
        self._on_unhandled_error = on_unhandled_error
        threading.Thread(target=self._loop, daemon=True).start()
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(50)

    def run(self, func, on_success=None, on_error=None):
        """func بتتنفذ في الخلفية. on_success(result) / on_error(exception) في الواجهة."""
        self._pending += 1
        self._notify()
        self._tasks.put((func, on_success, on_error))

    def is_busy(self) -> bool:
        return self._pending > 0

    def add_busy_listener(self, callback):
        self._busy_listeners.append(callback)

    def clear_busy_listeners(self):
        self._busy_listeners.clear()

    # ---------- داخلي ----------

    def _loop(self):
        while True:
            func, on_success, on_error = self._tasks.get()
            try:
                self._results.put((on_success, on_error, func(), None))
            except Exception as e:  # noqa: BLE001 - أي خطأ بيرجع للواجهة تعرضه
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
                if error is not None:
                    (on_error or self._on_unhandled_error)(error)
                elif on_success:
                    on_success(result)
            except RuntimeError as e:
                # الشاشة اللي كانت مستنية النتيجة اتقفلت (مثلاً عمل خروج) - Qt بيرمي
                # "Internal C++ object already deleted"، ومفيش حاجة نعملها
                if "deleted" not in str(e):
                    self._on_unhandled_error(e)
            except Exception as e:  # noqa: BLE001
                self._on_unhandled_error(e)

    def _notify(self):
        for callback in list(self._busy_listeners):
            try:
                callback(self._pending > 0)
            except RuntimeError:
                pass
