import sys
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QGridLayout, QFrame, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit, QDialog,
    QFormLayout, QMessageBox, QHeaderView, QTabWidget, QScrollArea, QFrame,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QIcon

# --- Database Management (Full Schema) ---
class DatabaseManager:
    def __init__(self, db_name="tailor_erp_v3.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, category TEXT, unit TEXT, price REAL, stock REAL)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY, name TEXT, phone TEXT,
                shoulder REAL, chest REAL, waist REAL, length REAL, notes TEXT
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL, status TEXT, date TIMESTAMP)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY, customer_id INTEGER, suit_type TEXT,
                status TEXT DEFAULT 'pending', created_at TIMESTAMP
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, type TEXT, amount REAL, category TEXT, date TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY, name TEXT, role TEXT, salary REAL)")
        self.conn.commit()

# --- Main App ---
class OdooStyleERP(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tailor Master ERP - النسخة المطورة")
        self.resize(1300, 850)
        self.db = DatabaseManager()
        self.current_theme = "Odoo Soft"

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Top Navbar
        self.init_top_nav()

        # 2. Body
        self.body_container = QWidget()
        self.body_layout = QHBoxLayout(self.body_container)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        # Content Stack
        self.content_stack = QStackedWidget()
        self.body_layout.addWidget(self.content_stack)
        self.main_layout.addWidget(self.body_container)

        # Initialize Views
        self.init_app_switcher()   # Index 0
        self.init_manufacturing()  # Index 1
        self.init_inventory()      # Index 2
        self.init_sales()          # Index 3
        self.init_customers()      # Index 4
        self.init_accounting()     # Index 5
        self.init_hr()             # Index 6

        self.apply_theme(self.current_theme)

    def init_top_nav(self):
        self.top_nav = QFrame()
        self.top_nav.setFixedHeight(60)
        self.top_nav.setObjectName("TopNav")
        layout = QHBoxLayout(self.top_nav)
        layout.setContentsMargins(20, 0, 20, 0)

        self.btn_home = QPushButton("👔 Tailor Master")
        self.btn_home.setStyleSheet("font-weight: bold; font-size: 18px; color: white; background: transparent; border: none;")
        self.btn_home.clicked.connect(lambda: self.switch_page(0, "الرئيسية"))
        layout.addWidget(self.btn_home)

        layout.addSpacing(30)
        self.lbl_breadcrumb = QLabel("الرئيسية")
        self.lbl_breadcrumb.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
        layout.addWidget(self.lbl_breadcrumb)

        layout.addStretch()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Odoo Soft", "Dark Mode", "Navy & Amber"])
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        self.theme_combo.setFixedWidth(150)
        layout.addWidget(self.theme_combo)

    def switch_page(self, idx, title):
        self.content_stack.setCurrentIndex(idx)
        self.lbl_breadcrumb.setText(f"الرئيسية / {title}")

    def apply_theme(self, theme):
        self.current_theme = theme
        odoo_purple = "#714B67"
        if theme == "Dark Mode":
            bg, text, card = "#121212", "#E0E0E0", "#1E1E1E"
            style = f"""
                QMainWindow {{ background-color: {bg}; }}
                QFrame#TopNav {{ background-color: #1A1A1A; border-bottom: 1px solid #333; }}
                QLabel {{ color: {text}; font-family: 'Segoe UI'; }}
                QPushButton.app-btn {{ background-color: {card}; border: 1px solid #333; border-radius: 12px; color: {text}; font-size: 14px; }}
                QPushButton.app-btn:hover {{ background-color: #2D2D2D; border-color: #BB86FC; }}
                QPushButton.back-btn {{ background: #333; color: white; border: none; border-radius: 5px; padding: 8px 15px; font-weight: bold; }}
                QTableWidget {{ background-color: {card}; color: white; gridline-color: #333; }}
                QHeaderView::section {{ background-color: #1A1A1A; color: white; border: 1px solid #333; }}
            """
        elif theme == "Navy & Amber":
            style = """
                QMainWindow { background-color: #F8F9FA; }
                QFrame#TopNav { background-color: #1A237E; }
                QPushButton.app-btn { background-color: white; border: 2px solid #1A237E; border-radius: 12px; color: #1A237E; font-weight: bold; }
                QPushButton.app-btn:hover { background-color: #FF6D00; color: white; border-color: #FF6D00; }
                QPushButton.back-btn { background: #1A237E; color: white; border-radius: 5px; padding: 8px 15px; }
            """
        else: # Odoo Soft
            style = f"""
                QMainWindow {{ background-color: #F0F2F5; }}
                QFrame#TopNav {{ background-color: {odoo_purple}; }}
                QLabel {{ color: #212529; font-family: 'Segoe UI'; }}
                QPushButton.app-btn {{ background-color: white; border: 1px solid #DEE2E6; border-radius: 15px; font-weight: bold; color: #444; font-size: 14px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
                QPushButton.app-btn:hover {{ border-color: {odoo_purple}; background-color: #F8F9FA; transform: translateY(-2px); }}
                QPushButton.back-btn {{ background: #f8f9fa; color: {odoo_purple}; border: 1px solid #DEE2E6; border-radius: 6px; padding: 8px 20px; font-weight: bold; }}
                QPushButton.back-btn:hover {{ background: #eee; }}
                QPushButton.action-btn {{ background: {odoo_purple}; color: white; border: none; border-radius: 6px; padding: 8px 20px; font-weight: bold; }}
                QTableWidget {{ background-color: white; border-radius: 8px; border: 1px solid #DEE2E6; }}
            """
        self.setStyleSheet(style)

    def create_header(self, title, back_callback):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 10)

        btn_back = QPushButton("← رجوع للرئيسية")
        btn_back.setProperty("class", "back-btn")
        btn_back.clicked.connect(back_callback)
        layout.addWidget(btn_back)

        layout.addSpacing(20)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(lbl_title)

        layout.addStretch()
        return container

    # --- App Switcher (0) ---
    def init_app_switcher(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 60, 60, 60)

        title = QLabel("لوحة التطبيقات")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(35)
        apps = [
            ("التصنيع", 1, "✂️"), ("المخازن", 2, "📦"), ("المبيعات", 3, "🧾"),
            ("العملاء", 4, "👔"), ("الحسابات", 5, "💰"), ("الموارد البشرية", 6, "👥")
        ]
        for i, (name, idx, icon) in enumerate(apps):
            btn = QPushButton(f"{icon}\n\n{name}")
            btn.setFixedSize(200, 160)
            btn.setProperty("class", "app-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, id=idx, t=name: self.switch_page(id, t))
            grid.addWidget(btn, i // 3, i % 3)

        layout.addLayout(grid)
        layout.addStretch()
        self.content_stack.addWidget(page)

    # --- Manufacturing (1) ---
    def init_manufacturing(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("إدارة خطوط الإنتاج", lambda: self.switch_page(0, "الرئيسية")))

        # Kanban Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        k_layout = QHBoxLayout(content)
        k_layout.setContentsMargins(20, 10, 20, 20)
        k_layout.setSpacing(15)

        stages = [("قيد الانتظار", "#FFC107"), ("مرحلة القص", "#2196F3"), ("الخياطة", "#9C27B0"), ("التشطيب", "#4CAF50"), ("جاهز", "#2E7D32")]
        for name, color in stages:
            col = QFrame()
            col.setFixedWidth(260)
            col.setStyleSheet(f"background: #EBEDF0; border-radius: 8px; border-top: 5px solid {color};")
            cl = QVBoxLayout(col)
            cl.addWidget(QLabel(f"<b>{name}</b>"))
            cl.addStretch()
            k_layout.addWidget(col)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.content_stack.addWidget(page)

    # --- Inventory (2) ---
    def init_inventory(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("المخازن والخامات", lambda: self.switch_page(0, "الرئيسية")))

        inner = QVBoxLayout()
        inner.setContentsMargins(20, 0, 20, 20)
        btn_add = QPushButton("+ إضافة خامة جديدة")
        btn_add.setProperty("class", "action-btn")
        inner.addWidget(btn_add, alignment=Qt.AlignRight)

        table = QTableWidget(15, 6)
        table.setHorizontalHeaderLabels(["الكود", "الاسم", "الفئة", "الوحدة", "السعر", "المخزون"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        inner.addWidget(table)
        layout.addLayout(inner)
        self.content_stack.addWidget(page)

    # --- Sales (3) ---
    def init_sales(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("المبيعات والفواتير", lambda: self.switch_page(0, "الرئيسية")))
        table = QTableWidget(10, 5)
        table.setHorizontalHeaderLabels(["رقم الفاتورة", "العميل", "التاريخ", "الإجمالي", "الحالة"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        self.content_stack.addWidget(page)

    # --- Customers (4) ---
    def init_customers(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("سجل العملاء والمقاسات", lambda: self.switch_page(0, "الرئيسية")))
        table = QTableWidget(10, 6)
        table.setHorizontalHeaderLabels(["الاسم", "الهاتف", "الكتف", "الصدر", "الوسط", "ملاحظات"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        self.content_stack.addWidget(page)

    # --- Accounting (5) ---
    def init_accounting(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("الحسابات والخزينة", lambda: self.switch_page(0, "الرئيسية")))
        layout.addStretch()
        self.content_stack.addWidget(page)

    # --- HR (6) ---
    def init_hr(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_header("الموارد البشرية والعاملين", lambda: self.switch_page(0, "الرئيسية")))
        table = QTableWidget(10, 4)
        table.setHorizontalHeaderLabels(["الموظف", "الوظيفة", "الراتب", "الحالة"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        self.content_stack.addWidget(page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    window = OdooStyleERP()
    window.show()
    sys.exit(app.exec())
