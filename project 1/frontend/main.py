import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QGridLayout, QFrame, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit, QDialog,
    QFormLayout, QDoubleSpinBox, QSpinBox, QMessageBox, QHeaderView,
    QTabWidget, QSplitter, QScrollArea
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon

class OdooERPMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نظام إدارة مصانع ومحلات البدل - ERP")
        self.resize(1400, 850)
        self.API_URL = "http://127.0.0.1:8000"
        self.current_theme = "Odoo Soft"

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.init_sidebar(main_layout)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.init_top_navbar(right_layout)

        self.content_stack = QStackedWidget()
        self.init_dashboard_view()
        self.init_manufacturing_kanban()
        self.init_inventory_view()
        self.init_sales_view()
        self.init_customers_view()
        self.init_accounting_view()
        self.init_hr_view()

        right_layout.addWidget(self.content_stack)
        main_layout.addWidget(right_container, 5)

        self.apply_theme(self.current_theme)

    def apply_theme(self, theme_name):
        self.current_theme = theme_name

        if theme_name == "Odoo Soft":
            self.setStyleSheet("""
                QMainWindow { background-color: #F8F9FA; }
                QWidget { color: #212529; font-family: 'Segoe UI', Tahoma; }
                QFrame#Sidebar { background-color: #FFFFFF; border-right: 1px solid #DEE2E6; }
                QLabel#LogoLabel { color: #714B67; font-size: 18px; font-weight: bold; padding: 20px; border-bottom: 1px solid #DEE2E6; }
                QPushButton.sidebar-btn { background-color: transparent; border: none; color: #343A40; text-align: right; padding: 14px 18px; font-size: 14px; border-radius: 6px; margin: 3px 12px; }
                QPushButton.sidebar-btn:hover { background-color: #F1F3F5; color: #714B67; font-weight: bold; }
                QPushButton.sidebar-btn:pressed { background-color: #E9ECEF; }
                QFrame#TopNav { background-color: #FFFFFF; border-bottom: 1px solid #DEE2E6; min-height: 60px; }
                QLabel#Breadcrumb { color: #495057; font-size: 14px; font-weight: bold; }
                QLineEdit#SearchBox { background-color: #F8F9FA; border: 1px solid #CED4DA; border-radius: 6px; padding: 6px 12px; color: #495057; min-width: 200px; }
                QComboBox#ThemeSelector { background-color: #FFFFFF; border: 1px solid #CED4DA; border-radius: 6px; padding: 6px 12px; color: #495057; min-width: 150px; }
                QPushButton.app-tile { background-color: #FFFFFF; border: 1px solid #DEE2E6; border-radius: 10px; font-size: 14px; font-weight: bold; color: #343A40; }
                QPushButton.app-tile:hover { background-color: #F8F9FA; border-color: #714B67; color: #714B67; }
                QFrame.kanban-col { background-color: #FFFFFF; border: 1px solid #DEE2E6; border-radius: 8px; }
                QFrame.kanban-card { background-color: #F8F9FA; border: 1px solid #CED4DA; border-radius: 6px; padding: 12px; }
                QLabel.kanban-header { color: #714B67; font-size: 14px; font-weight: bold; border-bottom: 2px solid #F1F3F5; padding-bottom: 10px; margin-bottom: 10px; }
                QTableWidget { background-color: #FFFFFF; border: 1px solid #DEE2E6; gridline-color: #E9ECEF; }
                QTableWidget::item { padding: 8px; }
                QTableWidget::item:selected { background-color: #E7F5FF; }
                QPushButton.primary-btn { background-color: #714B67; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.primary-btn:hover { background-color: #5c3b53; }
                QPushButton.secondary-btn { background-color: #6C757D; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.secondary-btn:hover { background-color: #5a6268; }
            """)
        elif theme_name == "Navy & Amber":
            self.setStyleSheet("""
                QMainWindow { background-color: #E9ECEF; }
                QWidget { color: #1A237E; font-family: 'Segoe UI', Tahoma; }
                QFrame#Sidebar { background-color: #1A237E; border-right: 1px solid #303F9F; }
                QLabel#LogoLabel { color: #FFFFFF; font-size: 18px; font-weight: bold; padding: 20px; border-bottom: 1px solid #303F9F; }
                QPushButton.sidebar-btn { background-color: transparent; border: none; color: #E8EAF6; text-align: right; padding: 14px 18px; font-size: 14px; border-radius: 6px; margin: 3px 12px; }
                QPushButton.sidebar-btn:hover { background-color: #303F9F; color: #FF6D00; font-weight: bold; }
                QFrame#TopNav { background-color: #FFFFFF; border-bottom: 1px solid #CED4DA; min-height: 60px; }
                QLabel#Breadcrumb { color: #1A237E; font-size: 14px; font-weight: bold; }
                QLineEdit#SearchBox { background-color: #F8F9FA; border: 1px solid #1A237E; border-radius: 6px; padding: 6px 12px; color: #1A237E; min-width: 200px; }
                QComboBox#ThemeSelector { background-color: #FFFFFF; border: 1px solid #1A237E; border-radius: 6px; padding: 6px 12px; color: #1A237E; min-width: 150px; }
                QPushButton.app-tile { background-color: #FFFFFF; border: 2px solid #1A237E; border-radius: 10px; font-size: 14px; font-weight: bold; color: #1A237E; }
                QPushButton.app-tile:hover { background-color: #FF6D00; border-color: #FF6D00; color: #FFFFFF; }
                QFrame.kanban-col { background-color: #FFFFFF; border: 1px solid #CED4DA; border-radius: 8px; }
                QFrame.kanban-card { background-color: #FFF8E1; border: 1px solid #1A237E; border-radius: 6px; padding: 12px; }
                QLabel.kanban-header { color: #1A237E; font-size: 14px; font-weight: bold; border-bottom: 2px solid #E9ECEF; padding-bottom: 10px; margin-bottom: 10px; }
                QTableWidget { background-color: #FFFFFF; border: 1px solid #1A237E; gridline-color: #E9ECEF; }
                QTableWidget::item { padding: 8px; }
                QTableWidget::item:selected { background-color: #FFE0B2; }
                QPushButton.primary-btn { background-color: #FF6D00; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.primary-btn:hover { background-color: #E65100; }
                QPushButton.secondary-btn { background-color: #1A237E; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.secondary-btn:hover { background-color: #0D1557; }
            """)
        elif theme_name == "Dark Mode":
            self.setStyleSheet("""
                QMainWindow { background-color: #121212; }
                QWidget { color: #E0E0E0; font-family: 'Segoe UI', Tahoma; }
                QFrame#Sidebar { background-color: #1E1E1E; border-right: 1px solid #2D2D2D; }
                QLabel#LogoLabel { color: #BB86FC; font-size: 18px; font-weight: bold; padding: 20px; border-bottom: 1px solid #2D2D2D; }
                QPushButton.sidebar-btn { background-color: transparent; border: none; color: #E0E0E0; text-align: right; padding: 14px 18px; font-size: 14px; border-radius: 6px; margin: 3px 12px; }
                QPushButton.sidebar-btn:hover { background-color: #2D2D2D; color: #BB86FC; font-weight: bold; }
                QFrame#TopNav { background-color: #1E1E1E; border-bottom: 1px solid #2D2D2D; min-height: 60px; }
                QLabel#Breadcrumb { color: #E0E0E0; font-size: 14px; font-weight: bold; }
                QLineEdit#SearchBox { background-color: #2D2D2D; border: 1px solid #444444; border-radius: 6px; padding: 6px 12px; color: #FFFFFF; min-width: 200px; }
                QComboBox#ThemeSelector { background-color: #2D2D2D; border: 1px solid #444444; border-radius: 6px; padding: 6px 12px; color: #FFFFFF; min-width: 150px; }
                QPushButton.app-tile { background-color: #1E1E1E; border: 1px solid #333333; border-radius: 10px; font-size: 14px; font-weight: bold; color: #FFFFFF; }
                QPushButton.app-tile:hover { background-color: #2A2A2A; border-color: #BB86FC; color: #BB86FC; }
                QFrame.kanban-col { background-color: #1E1E1E; border: 1px solid #333333; border-radius: 8px; }
                QFrame.kanban-card { background-color: #252525; border: 1px solid #333333; border-radius: 6px; padding: 12px; }
                QLabel.kanban-header { color: #BB86FC; font-size: 14px; font-weight: bold; border-bottom: 2px solid #2D2D2D; padding-bottom: 10px; margin-bottom: 10px; }
                QTableWidget { background-color: #1E1E1E; border: 1px solid #333333; gridline-color: #2D2D2D; color: #E0E0E0; }
                QTableWidget::item { padding: 8px; }
                QTableWidget::item:selected { background-color: #333333; }
                QPushButton.primary-btn { background-color: #BB86FC; color: #121212; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.primary-btn:hover { background-color: #996EFF; }
                QPushButton.secondary-btn { background-color: #444444; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold; }
                QPushButton.secondary-btn:hover { background-color: #555555; }
            """)

    def init_sidebar(self, parent_layout):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)

        logo = QLabel("👔 نظام البدلات ERP")
        logo.setObjectName("LogoLabel")
        layout.addWidget(logo)

        nav_items = [
            ("🏠 الرئيسية", lambda: self.content_stack.setCurrentIndex(0)),
            ("️ التصنيع", lambda: self.content_stack.setCurrentIndex(1)),
            ("📦 المخازن", lambda: self.content_stack.setCurrentIndex(2)),
            ("🧾 المبيعات", lambda: self.content_stack.setCurrentIndex(3)),
            ("👔 العملاء", lambda: self.content_stack.setCurrentIndex(4)),
            ("💰 الحسابات", lambda: self.content_stack.setCurrentIndex(5)),
            ("👥 الموارد البشرية", lambda: self.content_stack.setCurrentIndex(6)),
        ]

        for text, callback in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "sidebar-btn")
            btn.setMinimumHeight(45)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        layout.addStretch()
        parent_layout.addWidget(sidebar)

    def init_top_navbar(self, parent_layout):
        nav = QFrame()
        nav.setObjectName("TopNav")
        nav.setFixedHeight(60)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(20, 0, 20, 0)

        self.breadcrumb_label = QLabel("الرئيسية / لوحة التحكم")
        self.breadcrumb_label.setObjectName("Breadcrumb")
        layout.addWidget(self.breadcrumb_label)

        layout.addStretch()

        search_box = QLineEdit()
        search_box.setObjectName("SearchBox")
        search_box.setPlaceholderText("بحث سريع...")
        search_box.setFixedWidth(250)
        layout.addWidget(search_box)

        theme_selector = QComboBox()
        theme_selector.setObjectName("ThemeSelector")
        theme_selector.addItems(["Odoo Soft", "Navy & Amber", "Dark Mode"])
        theme_selector.setCurrentText(self.current_theme)
        theme_selector.currentTextChanged.connect(self.apply_theme)
        layout.addWidget(theme_selector)

        parent_layout.addWidget(nav)

    def init_dashboard_view(self):
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        title = QLabel("لوحة التطبيقات الرئيسية")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(title)

        subtitle = QLabel("اختر القسم الذي تريد الدخول إليه")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet("color: #6C757D;")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(25)

        apps = [
            ("التصنيع وأوامر التشغيل", lambda: self.switch_to_section(1), "✂️"),
            ("المخازن والخامات", lambda: self.switch_to_section(2), "📦"),
            ("المبيعات وعروض الأسعار", lambda: self.switch_to_section(3), "🧾"),
            ("العملاء والمقاسات", lambda: self.switch_to_section(4), "👔"),
            ("الحسابات والخزينة", lambda: self.switch_to_section(5), "💰"),
            ("الموارد البشرية", lambda: self.switch_to_section(6), ""),
        ]

        for i, (name, callback, icon) in enumerate(apps):
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setAlignment(Qt.AlignCenter)

            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Segoe UI", 36))
            icon_label.setAlignment(Qt.AlignCenter)
            tile_layout.addWidget(icon_label)

            name_label = QLabel(name)
            name_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(True)
            tile_layout.addWidget(name_label)

            btn = QPushButton(tile)
            btn.setProperty("class", "app-tile")
            btn.setFixedSize(220, 160)
            btn.clicked.connect(callback)

            tile_layout.addWidget(btn)

            grid.addWidget(tile, i // 3, i % 3)

        layout.addLayout(grid)
        layout.addStretch()

        scroll.setWidget(content)
        self.content_stack.addWidget(scroll)

    def init_manufacturing_kanban(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("إدارة التصنيع وأوامر التشغيل")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        new_order_btn = QPushButton("+ أمر تشغيل جديد")
        new_order_btn.setProperty("class", "primary-btn")
        new_order_btn.clicked.connect(self.open_new_order_dialog)
        header_layout.addWidget(new_order_btn)
        layout.addLayout(header_layout)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)

        stages = [
            ("قيد الانتظار", "#FFC107"),
            ("مرحلة القص", "#2196F3"),
            ("الخياطة والتجميع", "#9C27B0"),
            ("التشطيب والجودة", "#FF9800"),
            ("مكتمل وجاهز", "#4CAF50"),
        ]

        for stage_name, color in stages:
            col_frame = QFrame()
            col_frame.setProperty("class", "kanban-col")
            col_frame.setFixedWidth(250)
            col_layout = QVBoxLayout(col_frame)
            col_layout.setContentsMargins(12, 12, 12, 12)
            col_layout.setSpacing(10)

            header = QLabel(f"{stage_name} (0)")
            header.setProperty("class", "kanban-header")
            header.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
            col_layout.addWidget(header)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)

            cards_widget = QWidget()
            cards_layout = QVBoxLayout(cards_widget)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(8)

            sample_cards = [
                ("بدلة كلاسيك - كحلي", "العميل: أحمد محمد", "مقاس: 48 - صوف فاخر"),
                ("بدلة رسمية - رمادي", "العميل: خالد علي", "مقاس: 50 - قماش إيطالي"),
            ]

            for card_title, card_client, card_details in sample_cards:
                card = QFrame()
                card.setProperty("class", "kanban-card")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 10, 10, 10)
                card_layout.setSpacing(6)

                title_label = QLabel(card_title)
                title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
                card_layout.addWidget(title_label)

                client_label = QLabel(card_client)
                client_label.setFont(QFont("Segoe UI", 10))
                client_label.setStyleSheet("color: #6C757D;")
                card_layout.addWidget(client_label)

                details_label = QLabel(card_details)
                details_label.setFont(QFont("Segoe UI", 9))
                details_label.setStyleSheet("color: #868E96; font-style: italic;")
                card_layout.addWidget(details_label)

                cards_layout.addWidget(card)

            cards_layout.addStretch()
            scroll.setWidget(cards_widget)
            col_layout.addWidget(scroll)

            columns_layout.addWidget(col_frame)

        layout.addLayout(columns_layout)
        self.content_stack.addWidget(widget)

    def init_inventory_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("إدارة المخازن والخامات")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        add_material_btn = QPushButton("+ خامة جديدة")
        add_material_btn.setProperty("class", "primary-btn")
        header_layout.addWidget(add_material_btn)
        layout.addLayout(header_layout)

        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["الكود", "الاسم", "الفئة", "الوحدة", "السعر", "المخزون", "حد الطلب"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(400)

        sample_data = [
            ["FAB001", "صوف إيطالي فاخر", "أقمشة", "متر", "150.00", "250", "50"],
            ["BTN001", "أزرار عرق اللؤلؤ", "إكسسوارات", "قطعة", "2.50", "1000", "200"],
            ["LIN001", "بطانة حريرية", "بطانات", "متر", "25.00", "180", "30"],
        ]

        table.setRowCount(len(sample_data))
        for row_idx, row_data in enumerate(sample_data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        layout.addWidget(table)
        self.content_stack.addWidget(widget)

    def init_sales_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("المبيعات وعروض الأسعار")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        new_invoice_btn = QPushButton("+ فاتورة جديدة")
        new_invoice_btn.setProperty("class", "primary-btn")
        header_layout.addWidget(new_invoice_btn)
        layout.addLayout(header_layout)

        tabs = QTabWidget()

        invoices_tab = QWidget()
        invoices_layout = QVBoxLayout(invoices_tab)

        invoice_table = QTableWidget()
        invoice_table.setColumnCount(6)
        invoice_table.setHorizontalHeaderLabels(["رقم الفاتورة", "العميل", "التاريخ", "الإجمالي", "الحالة", "المدفوع"])
        invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        invoice_table.setAlternatingRowColors(True)
        invoice_table.setMinimumHeight(350)

        sample_invoices = [
            ["INV-001", "أحمد محمد", "2024-10-15", "2500.00", "مكتملة", "2500.00"],
            ["INV-002", "خالد علي", "2024-10-18", "1800.00", "قيد الانتظار", "900.00"],
        ]

        invoice_table.setRowCount(len(sample_invoices))
        for row_idx, row_data in enumerate(sample_invoices):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                invoice_table.setItem(row_idx, col_idx, item)

        invoices_layout.addWidget(invoice_table)
        tabs.addTab(invoices_tab, "الفواتير")

        quotes_tab = QWidget()
        quotes_layout = QVBoxLayout(quotes_tab)

        quote_table = QTableWidget()
        quote_table.setColumnCount(5)
        quote_table.setHorizontalHeaderLabels(["رقم العرض", "العميل", "التاريخ", "الإجمالي", "الحالة"])
        quote_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        quote_table.setAlternatingRowColors(True)
        quote_table.setMinimumHeight(350)

        sample_quotes = [
            ["QT-001", "محمد حسن", "2024-10-20", "3200.00", "مسودة"],
        ]

        quote_table.setRowCount(len(sample_quotes))
        for row_idx, row_data in enumerate(sample_quotes):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                quote_table.setItem(row_idx, col_idx, item)

        quotes_layout.addWidget(quote_table)
        tabs.addTab(quotes_tab, "عروض الأسعار")

        layout.addWidget(tabs)
        self.content_stack.addWidget(widget)

    def init_customers_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("العملاء والمقاسات")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        add_customer_btn = QPushButton("+ عميل جديد")
        add_customer_btn.setProperty("class", "primary-btn")
        header_layout.addWidget(add_customer_btn)
        layout.addLayout(header_layout)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["الاسم", "الهاتف", "البريد الإلكتروني", "آخر زيارة", "عدد الطلبات", "إجمالي المشتريات"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(400)

        sample_customers = [
            ["أحمد محمد", "010-12345678", "ahmed@email.com", "2024-10-15", "5", "12500.00"],
            ["خالد علي", "011-87654321", "khaled@email.com", "2024-10-18", "3", "7200.00"],
            ["محمد حسن", "012-11223344", "mohamed@email.com", "2024-10-10", "8", "18900.00"],
        ]

        table.setRowCount(len(sample_customers))
        for row_idx, row_data in enumerate(sample_customers):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        layout.addWidget(table)
        self.content_stack.addWidget(widget)

    def init_accounting_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("الحسابات والخزينة")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        add_transaction_btn = QPushButton("+ عملية مالية")
        add_transaction_btn.setProperty("class", "primary-btn")
        header_layout.addWidget(add_transaction_btn)
        layout.addLayout(header_layout)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(20)

        income_card = QFrame()
        income_card.setProperty("class", "kanban-col")
        income_layout = QVBoxLayout(income_card)
        income_layout.addWidget(QLabel("إجمالي الإيرادات"))
        amount_label = QLabel("45,200.00 ج.م")
        amount_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        amount_label.setStyleSheet("color: #4CAF50;")
        income_layout.addWidget(amount_label)
        summary_layout.addWidget(income_card)

        expense_card = QFrame()
        expense_card.setProperty("class", "kanban-col")
        expense_layout = QVBoxLayout(expense_card)
        expense_layout.addWidget(QLabel("إجمالي المصروفات"))
        exp_amount_label = QLabel("18,500.00 ج.م")
        exp_amount_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        exp_amount_label.setStyleSheet("color: #F44336;")
        expense_layout.addWidget(exp_amount_label)
        summary_layout.addWidget(expense_card)

        balance_card = QFrame()
        balance_card.setProperty("class", "kanban-col")
        balance_layout = QVBoxLayout(balance_card)
        balance_layout.addWidget(QLabel("صافي الربح"))
        bal_amount_label = QLabel("26,700.00 ج.م")
        bal_amount_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        bal_amount_label.setStyleSheet("color: #2196F3;")
        balance_layout.addWidget(bal_amount_label)
        summary_layout.addWidget(balance_card)

        layout.addLayout(summary_layout)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["التاريخ", "النوع", "الفئة", "الوصف", "المبلغ"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(300)

        sample_transactions = [
            ["2024-10-15", "إيراد", "مبيعات", "فاتورة #INV-001", "+2500.00"],
            ["2024-10-16", "مصروف", "رواتب", "رواتب العمال", "-1200.00"],
            ["2024-10-17", "إيراد", "مبيعات", "فاتورة #INV-002", "+1800.00"],
        ]

        table.setRowCount(len(sample_transactions))
        for row_idx, row_data in enumerate(sample_transactions):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        layout.addWidget(table)
        self.content_stack.addWidget(widget)

    def init_hr_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("الموارد البشرية")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        add_employee_btn = QPushButton("+ موظف جديد")
        add_employee_btn.setProperty("class", "primary-btn")
        header_layout.addWidget(add_employee_btn)
        layout.addLayout(header_layout)

        tabs = QTabWidget()

        employees_tab = QWidget()
        emp_layout = QVBoxLayout(employees_tab)

        emp_table = QTableWidget()
        emp_table.setColumnCount(5)
        emp_table.setHorizontalHeaderLabels(["الاسم", "الوظيفة", "الهاتف", "تاريخ التعيين", "الراتب"])
        emp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        emp_table.setAlternatingRowColors(True)
        emp_table.setMinimumHeight(350)

        sample_employees = [
            ["أحمد سعيد", "خياط رئيسي", "010-11111111", "2023-01-15", "5000.00"],
            ["محمد علي", "مساعد خياط", "011-22222222", "2023-06-01", "3000.00"],
        ]

        emp_table.setRowCount(len(sample_employees))
        for row_idx, row_data in enumerate(sample_employees):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                emp_table.setItem(row_idx, col_idx, item)

        emp_layout.addWidget(emp_table)
        tabs.addTab(employees_tab, "الموظفين")

        payroll_tab = QWidget()
        payroll_layout = QVBoxLayout(payroll_tab)

        payroll_table = QTableWidget()
        payroll_table.setColumnCount(5)
        payroll_table.setHorizontalHeaderLabels(["الموظف", "الشهر", "الساعات", "الإنتاجية", "الصافي"])
        payroll_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        payroll_table.setAlternatingRowColors(True)
        payroll_table.setMinimumHeight(350)

        sample_payroll = [
            ["أحمد سعيد", "أكتوبر 2024", "160", "45 بدلة", "5500.00"],
            ["محمد علي", "أكتوبر 2024", "160", "30 بدلة", "3400.00"],
        ]

        payroll_table.setRowCount(len(sample_payroll))
        for row_idx, row_data in enumerate(sample_payroll):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)
                payroll_table.setItem(row_idx, col_idx, item)

        payroll_layout.addWidget(payroll_table)
        tabs.addTab(payroll_tab, "كشف الرواتب")

        layout.addWidget(tabs)
        self.content_stack.addWidget(widget)

    def switch_to_section(self, index):
        self.content_stack.setCurrentIndex(index)
        section_names = ["الرئيسية", "التصنيع", "المخازن", "المبيعات", "العملاء", "الحسابات", "الموارد البشرية"]
        if 0 <= index < len(section_names):
            self.breadcrumb_label.setText(f"الرئيسية / {section_names[index]}")

    def open_new_order_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("أمر تشغيل جديد")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QFormLayout(dialog)

        customer_input = QLineEdit()
        customer_input.setPlaceholderText("اسم العميل")
        layout.addRow("العميل:", customer_input)

        suit_type_input = QLineEdit()
        suit_type_input.setPlaceholderText("مثال: بدلة كلاسيك - كحلي")
        layout.addRow("نوع البدلة:", suit_type_input)

        size_input = QLineEdit()
        size_input.setPlaceholderText("مثال: 48")
        layout.addRow("المقاس:", size_input)

        notes_input = QTextEdit()
        notes_input.setPlaceholderText("ملاحظات إضافية...")
        notes_input.setMaximumHeight(80)
        layout.addRow("ملاحظات:", notes_input)

        button_layout = QHBoxLayout()

        save_btn = QPushButton("حفظ")
        save_btn.setProperty("class", "primary-btn")
        save_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setProperty("class", "secondary-btn")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addRow(button_layout)

        if dialog.exec():
            QMessageBox.information(self, "نجاح", "تم حفظ أمر التشغيل بنجاح!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OdooERPMainWindow()
    window.show()
    sys.exit(app.exec())