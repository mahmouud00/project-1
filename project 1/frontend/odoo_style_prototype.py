import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QGridLayout, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

class OdooStyleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نظام إدارة البدل - ERP (Odoo Style)")
        self.resize(1200, 750)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #212529;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QPushButton.app-tile {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 12px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: #343a40;
            }
            QPushButton.app-tile:hover {
                background-color: #e9ecef;
                border-color: #714B67; /* لون مميز يشبه طابع أودو */
            }
            QPushButton.nav-btn {
                background-color: #714B67;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton.nav-btn:hover {
                background-color: #5c3b53;
            }
        """)

        # الـ Stack لتغيير الشاشات (بين شاشة التطبيقات والشاشات الداخلية)
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # إنشاء الشاشات
        self.init_app_switcher()
        self.init_kanban_view()

    def init_app_switcher(self):
        """شاشة التطبيقات الرئيسية (شبكة مربعات)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("لوحة التطبيقات الرئيسية")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(20)

        apps = [
            ("المبيعات وعروض الأسعار", self.open_sales),
            ("التصنيع وأوامر التشغيل", self.open_manufacturing),
            ("إدارة المخازن والخامات", self.open_inventory),
            ("الحسابات والخزينة", self.open_accounting),
            ("شؤون العاملين (HR)", self.open_hr),
            ("العملاء والمقاسات (CRM)", self.open_crm)
        ]

        for i, (app_name, callback) in enumerate(apps):
            btn = QPushButton(app_name)
            btn.setProperty("class", "app-tile")
            btn.setFixedSize(180, 140)
            btn.clicked.connect(callback)
            grid.addWidget(btn, i // 3, i % 3)

        layout.addLayout(grid)
        self.central_stack.addWidget(widget)

    def init_kanban_view(self):
        """شاشة التصنيع - عرض Kanban (أعمدة مراحل الإنتاج)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # شريط علوي للشاشة
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← عودة للقائمة الرئيسية")
        back_btn.setProperty("class", "nav-btn")
        back_btn.clicked.connect(lambda: self.central_stack.setCurrentIndex(0))

        screen_title = QLabel("إدارة التصنيع - لوحة أوامر التشغيل (Kanban)")
        screen_title.setFont(QFont("Segoe UI", 16, QFont.Bold))

        top_bar.addWidget(back_btn)
        top_bar.addStretch()
        top_bar.addWidget(screen_title)
        layout.addLayout(top_bar)

        # منطقة الأعمدة
        columns_layout = QHBoxLayout()
        stages = ["قيد الانتظار", "مرحلة القص", "الخياطة والتجميع", "التشطيب والجودة", "مكتمل وجاهز"]

        for stage in stages:
            col_frame = QFrame()
            col_frame.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 8px;
                }
            """)
            col_layout = QVBoxLayout(col_frame)

            header = QLabel(stage)
            header.setFont(QFont("Segoe UI", 12, QFont.Bold))
            header.setStyleSheet("color: #714B67; border: none;")
            col_layout.addWidget(header)

            # بطاقات تجريبية داخل العمود
            for j in range(2):
                card = QLabel(f"بدلة كحلي - عميل #{j+1}\nمقاس: 48 - تفصيل خاص")
                card.setStyleSheet("""
                    QLabel {
                        background-color: #f1f3f5;
                        border: 1px solid #adb5bd;
                        border-radius: 6px;
                        padding: 10px;
                        margin: 4px 0px;
                        color: #495057;
                    }
                """)
                col_layout.addWidget(card)

            col_layout.addStretch()
            columns_layout.addWidget(col_frame)

        layout.addLayout(columns_layout)
        self.central_stack.addWidget(widget)

    def open_sales(self):
        print("فتح قسم المبيعات")

    def open_manufacturing(self):
        # الانتقال لشاشة التصنيع (Kanban)
        self.central_stack.setCurrentIndex(1)

    def open_inventory(self):
        print("فتح قسم المخازن")

    def open_accounting(self):
        print("فتح قسم الحسابات")

    def open_hr(self):
        print("فتح قسم الموارد البشرية")

    def open_crm(self):
        print("فتح قسم العملاء")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OdooStyleApp()
    window.show()
    sys.exit(app.exec())
