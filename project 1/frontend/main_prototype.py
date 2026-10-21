import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget

class ERPMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نظام إدارة البدل - ERP System")
        self.resize(1000, 700)

        # الواجهة الرئيسية
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # القائمة الجانبية (Sidebar)
        sidebar = QVBoxLayout()
        buttons = ["الرئيسية", "إدارة المخازن", "أوامر التشغيل", "المبيعات والعملاء", "الحسابات", "الإعدادات"]
        for btn_text in buttons:
            btn = QPushButton(btn_text)
            sidebar.addWidget(btn)
        sidebar.addStretch()

        # المنطقة الرئيسية (Content Area)
        self.content_area = QStackedWidget()
        self.content_area.addWidget(QLabel("مرحباً بك في نظام إدارة البدل. اختر قسماً من القائمة الجانبية."))

        main_layout.addLayout(sidebar, 1)
        main_layout.addWidget(self.content_area, 4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ERPMainWindow()
    window.show()
    sys.exit(app.exec())
