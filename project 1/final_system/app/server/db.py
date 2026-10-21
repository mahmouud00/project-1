"""
db.py — قاعدة البيانات (SQLite)
-------------------------------
ملف واحد على جهاز السيرفر فيه كل بيانات الشركة. النسخة الاحتياطية = نسخة من الملف ده.

- البرنامج بيعمل الجداول لوحده أول مرة (مفيش حاجة تتشغل بإيدك).
- SCHEMA_VERSION: لو غيّرنا الجداول فى إصدار جديد، MIGRATIONS بتحدّث القاعدة القديمة
  من غير ما البيانات تضيع.
"""

import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
create table if not exists meta (
    key    text primary key,
    value  text
);

-- ========================= الشركة والمستخدمين =========================

create table if not exists company (
    id                 integer primary key check (id = 1),     -- شركة واحدة بس فى كل قاعدة
    name               text not null check (length(trim(name)) > 0),
    phone              text,
    address            text,
    receipt_note       text,          -- كلام بيتطبع تحت الإيصال (مثلاً: البضاعة لا ترد بعد 30 يوم)
    logo               blob,
    logo_type          text,
    profit_start_date  text,
    require_attachment integer not null default 0,
    created_at         text not null default (datetime('now', 'localtime'))
);

create table if not exists users (
    id             integer primary key,
    username       text not null unique collate nocase check (length(trim(username)) > 0),
    full_name      text not null check (length(trim(full_name)) > 0),
    password_hash  text not null,
    role_title     text,
    is_active      integer not null default 1,
    is_admin       integer not null default 0,
    pages          text not null default '[]',      -- يشوف
    edit_pages     text not null default '[]',      -- يضيف ويعدّل
    delete_pages   text not null default '[]',      -- يمسح
    last_login     text,
    created_at     text not null default (datetime('now', 'localtime'))
);

create table if not exists branches (
    id       integer primary key,
    name     text not null unique check (length(trim(name)) > 0),
    is_main  integer not null default 0
);

-- ========================= القوائم (الإعدادات) =========================

create table if not exists payment_methods (
    id         integer primary key,
    name       text not null unique,
    channel    text not null check (channel in ('cash', 'bank', 'wallet', 'cheque')),
    sort       integer not null default 0,
    is_active  integer not null default 1
);

-- أنواع الشغل: بدلة 2 قطعة، بدلة 3 قطع، جاكيت، بنطلون...
create table if not exists garment_types (
    id             integer primary key,
    name           text not null unique,
    default_price  real not null default 0,
    sort           integer not null default 0,
    is_active      integer not null default 1
);

-- role: الإدارة اللى البرنامج بيستخدمها أوتوماتيك
--   sales = تحصيل الطلبات والبيع، payroll = الأجور والسلف، purchases = دفعات الموردين
create table if not exists departments (
    id         integer primary key,
    name       text not null unique,
    is_sales   integer not null default 0,     -- الوارد بيها = مبيعات (فى الربح)
    in_profit  integer not null default 0,     -- المنصرف بيها = تكلفة (فى الربح)
    role       text not null default '',
    sort       integer not null default 0,
    is_active  integer not null default 1
);

-- المقاسات اللى بتتاخد (كل شركة تعدّلها على مزاجها)
create table if not exists measure_fields (
    id         integer primary key,
    grp        text not null,                  -- جاكيت / بنطلون / صديري / قميص
    name       text not null,
    sort       integer not null default 0,
    is_active  integer not null default 1,
    unique (grp, name)
);

-- تفاصيل الموديل: الاسم + الاختيارات (سطر لكل اختيار)
create table if not exists style_options (
    id         integer primary key,
    name       text not null unique,
    choices    text not null default '',
    sort       integer not null default 0,
    is_active  integer not null default 1
);

-- أجر القطعة لكل مرحلة ونوع (للعمال اللى بيتحاسبوا بالقطعة)
create table if not exists piece_rates (
    id               integer primary key,
    garment_type_id  integer not null references garment_types on delete cascade,
    stage            text not null check (stage in ('cutting', 'sewing', 'finishing')),
    rate             real not null default 0 check (rate >= 0),
    unique (garment_type_id, stage)
);

-- ========================= الناس =========================

-- kind: sales = سيلز، worker = عامل فى المصنع، other = أخرى
-- pay_type: piece = بالقطعة، salary = مرتب، both = مرتب + قطعة
create table if not exists staff (
    id         integer primary key,
    name       text not null check (length(trim(name)) > 0),
    mobile     text,
    kind       text not null default 'worker' check (kind in ('sales', 'worker', 'other')),
    craft      text,                            -- قصاص، خياط، مكوجى...
    pay_type   text not null default 'piece' check (pay_type in ('piece', 'salary', 'both')),
    salary     real not null default 0 check (salary >= 0),
    hired_on   text,
    is_active  integer not null default 1,
    created_at text not null default (datetime('now', 'localtime')),
    unique (name, kind)
);

create table if not exists customers (
    id            integer primary key,
    name          text not null check (length(trim(name)) > 0),
    mobile        text,
    address       text,
    notes         text,
    measurements  text not null default '{}',   -- آخر مقاسات {"جاكيت|الطول": "76"}
    measured_at   text,
    created_at    text not null default (datetime('now', 'localtime'))
);
create index if not exists customers_mobile on customers (mobile);

create table if not exists measurements_history (
    id           integer primary key,
    customer_id  integer not null references customers on delete cascade,
    data         text not null,
    created_by   integer,
    created_at   text not null default (datetime('now', 'localtime'))
);

-- ========================= الموردين =========================

create table if not exists suppliers (
    id             integer primary key,
    name           text not null unique check (length(trim(name)) > 0),
    material       text,
    mobile         text,
    supplier_type  text,
    created_at     text not null default (datetime('now', 'localtime'))
);

-- ========================= الطلبات (التفصيل) =========================

create table if not exists orders (
    id                  integer primary key,
    branch_id           integer not null references branches,
    customer_id         integer not null references customers,
    garment_type_id     integer references garment_types,
    quantity            integer not null default 1 check (quantity > 0),
    price               real not null check (price > 0),
    deposit             real not null default 0 check (deposit >= 0),
    deposit_method_id   integer references payment_methods,
    seller_id           integer references staff,
    fabric_source       text not null default 'factory' check (fabric_source in ('factory', 'customer')),
    fabric_desc         text,
    measurements        text not null default '{}',
    style               text not null default '{}',
    notes               text,                 -- ملاحظات الطلب (بتتطبع فى ورقة المصنع)
    note                text,                 -- ملاحظة متابعة على المرحلة
    needs_fitting       integer not null default 1,
    fitting_count       integer not null default 0,
    due_date            text,                 -- ميعاد التسليم
    fitting_date        text,                 -- ميعاد البروفة
    status              text not null check (status in ('awaiting_deposit', 'cutting', 'sewing', 'fitting',
                            'finishing', 'ready', 'awaiting_accounts', 'completed')),
    attachments         text not null default '[]',   -- أرقام الملفات فى جدول files
    material_cost       real not null default 0,
    labor_cost          real not null default 0,
    final_collected     real check (final_collected >= 0),
    final_method_id     integer references payment_methods,
    created_by          integer,
    created_at          text not null default (datetime('now', 'localtime')),
    deposit_confirmed_at text,
    cut_at              text,
    sewn_at             text,
    fitted_at           text,
    finished_at         text,
    delivered_at        text,
    completed_at        text,
    completed_by        integer
);
create index if not exists orders_status on orders (status);

-- كل اللى حصل للطلب (مين عمل إيه وإمتى)
create table if not exists order_events (
    id          integer primary key,
    order_id    integer not null references orders on delete cascade,
    action      text not null,
    details     text,
    created_by  integer,
    created_at  text not null default (datetime('now', 'localtime'))
);

-- ========================= المخزن =========================

create table if not exists materials (
    id             integer primary key,
    name           text not null unique check (length(trim(name)) > 0),
    category       text,                        -- قماش، بطانة، زراير، خيط...
    unit           text not null default 'متر',
    qty            real not null default 0,
    avg_cost       real not null default 0,     -- متوسط سعر الوحدة
    reorder_level  real not null default 0,
    is_active      integer not null default 1,
    created_at     text not null default (datetime('now', 'localtime'))
);

-- qty موجبة = دخول، سالبة = خروج
create table if not exists material_moves (
    id           integer primary key,
    material_id  integer not null references materials on delete cascade,
    move_type    text not null check (move_type in ('in', 'out', 'adjust')),
    qty          real not null,
    unit_cost    real not null default 0,
    order_id     integer references orders on delete set null,
    supplier_id  integer references suppliers on delete set null,
    note         text,
    move_date    text not null default (date('now', 'localtime')),
    created_by   integer,
    created_at   text not null default (datetime('now', 'localtime'))
);

-- البدل الجاهزة
create table if not exists products (
    id               integer primary key,
    name             text not null check (length(trim(name)) > 0),
    garment_type_id  integer references garment_types,
    size             text,
    color            text,
    qty              integer not null default 0,
    cost             real not null default 0,
    price            real not null default 0,
    is_active        integer not null default 1,
    created_at       text not null default (datetime('now', 'localtime')),
    unique (name, size, color)
);

create table if not exists product_moves (
    id          integer primary key,
    product_id  integer not null references products on delete cascade,
    move_type   text not null check (move_type in ('in', 'sale', 'adjust', 'return')),
    qty         integer not null,
    unit_price  real not null default 0,
    sale_id     integer,
    note        text,
    created_by  integer,
    created_at  text not null default (datetime('now', 'localtime'))
);

-- ========================= الخزينة =========================

create table if not exists treasury_entries (
    id                 integer primary key,
    branch_id          integer not null references branches,
    entry_date         text not null default (date('now', 'localtime')),
    amount_in          real not null default 0 check (amount_in >= 0),
    amount_out         real not null default 0 check (amount_out >= 0),
    description        text not null check (length(trim(description)) > 0),
    payment_method_id  integer references payment_methods,
    department_id      integer references departments,
    counterparty       text,
    supplier_id        integer references suppliers on delete set null,
    order_id           integer references orders,
    source             text not null default 'manual' check (source in ('manual', 'supplier_payment', 'cheque',
                           'order_deposit', 'order_final', 'ready_sale', 'payroll')),
    created_by         integer,
    created_at         text not null default (datetime('now', 'localtime')),
    check ((amount_in > 0) <> (amount_out > 0))
);
create index if not exists treasury_date on treasury_entries (entry_date);

create table if not exists ready_sales (
    id                 integer primary key,
    branch_id          integer not null references branches,
    customer_id        integer references customers,
    total              real not null check (total > 0),
    method_id          integer references payment_methods,
    seller_id          integer references staff,
    treasury_entry_id  integer references treasury_entries,
    note               text,
    created_by         integer,
    created_at         text not null default (datetime('now', 'localtime'))
);

create table if not exists ready_sale_items (
    id          integer primary key,
    sale_id     integer not null references ready_sales on delete cascade,
    product_id  integer not null references products,
    qty         integer not null check (qty > 0),
    price       real not null check (price >= 0)
);

create table if not exists supplier_txns (
    id                 integer primary key,
    supplier_id        integer not null references suppliers on delete cascade,
    txn_date           text not null default (date('now', 'localtime')),
    txn_type           text not null check (txn_type in ('invoice', 'cash_payment', 'bank_payment', 'cheque', 'return')),
    description        text,
    amount             real not null check (amount > 0),
    cheque_no          text,
    due_date           text,
    cheque_status      text check (cheque_status in ('due', 'cashed')),
    -- لو القيد اتمسح من الخزينة، الحركة المرتبطة بيه تتمسح معاه
    treasury_entry_id  integer references treasury_entries on delete cascade,
    created_by         integer,
    created_at         text not null default (datetime('now', 'localtime')),
    check (txn_type <> 'cheque' or (due_date is not null and cheque_status is not null))
);

-- ========================= الأجور =========================

-- شغل العامل بالقطعة (بيتسجل أوتوماتيك لما المرحلة تخلص، أو بإيدك)
create table if not exists work_log (
    id          integer primary key,
    staff_id    integer not null references staff on delete cascade,
    order_id    integer references orders on delete set null,
    stage       text,
    description text,
    qty         real not null default 1,
    rate        real not null default 0,
    amount      real not null default 0 check (amount >= 0),
    work_month  text not null,                  -- 2026-10
    created_by  integer,
    created_at  text not null default (datetime('now', 'localtime'))
);

-- advance = سلفة، payment = صرف أجر، bonus = مكافأة، deduction = خصم
create table if not exists staff_txns (
    id                 integer primary key,
    staff_id           integer not null references staff on delete cascade,
    txn_type           text not null check (txn_type in ('advance', 'payment', 'bonus', 'deduction')),
    amount             real not null check (amount > 0),
    for_month          text not null,
    description        text,
    treasury_entry_id  integer references treasury_entries on delete cascade,
    created_by         integer,
    created_at         text not null default (datetime('now', 'localtime'))
);

-- ========================= ملفات وسجل =========================

create table if not exists files (
    id          integer primary key,
    name        text not null,
    mime        text,
    data        blob not null,
    created_at  text not null default (datetime('now', 'localtime'))
);

create table if not exists activity_log (
    id          integer primary key,
    user_id     integer,
    user_name   text,
    action      text not null,
    details     text,
    amount      real,
    created_at  text not null default (datetime('now', 'localtime'))
);
"""

# رقم الإصدار ← أوامر التحديث (لما نضيف أعمدة فى إصدارات جاية)
MIGRATIONS = {}


def connect(path) -> sqlite3.Connection:
    """اتصال واحد بيستخدمه السيرفر كله (تحت قفل). المعاملات (BEGIN/COMMIT) بنتحكم فيها بإيدينا."""
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma synchronous = normal")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
    version = int(row["value"]) if row else 0
    if version == 0:
        conn.execute("insert or replace into meta (key, value) values ('schema_version', ?)", (str(SCHEMA_VERSION),))
        return
    for v in range(version + 1, SCHEMA_VERSION + 1):
        for sql in MIGRATIONS.get(v, []):
            conn.execute(sql)
        conn.execute("update meta set value = ? where key = 'schema_version'", (str(v),))


def is_our_database(path) -> bool:
    """بيتأكد إن الملف ده نسخة احتياطية من البرنامج ده (قبل الاسترجاع)."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("select value from meta where key = 'schema_version'").fetchone()
            conn.execute("select count(*) from orders").fetchone()
            return row is not None and int(row[0]) <= SCHEMA_VERSION
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return False


# ========================= البيانات الافتراضية لشركة جديدة =========================
# المدير يقدر يعدّل أو يوقف أى حاجة فيهم من الإعدادات

DEFAULT_PAYMENT_METHODS = [("نقدى", "cash"), ("بنك", "bank"), ("انستاباى", "wallet"),
                           ("فودافون كاش", "wallet"), ("شيك", "cheque")]

DEFAULT_GARMENT_TYPES = ["بدلة 2 قطعة", "بدلة 3 قطع", "جاكيت", "بنطلون", "صديرى", "قميص", "أخرى"]

# (الاسم، وارده مبيعات، منصرفه تكلفة، الاستخدام الأوتوماتيك)
DEFAULT_DEPARTMENTS = [("مبيعات", 1, 1, "sales"), ("خامات ومشتريات", 0, 1, "purchases"),
                       ("أجور ومرتبات", 0, 1, "payroll"), ("إيجار ومرافق", 0, 1, ""),
                       ("مصاريف تشغيل", 0, 1, ""), ("إدارية", 0, 0, "")]

DEFAULT_MEASURE_FIELDS = {
    "جاكيت": ["الطول", "الكتف", "الصدر", "الوسط", "الهانش", "طول الكم", "عرض الكم", "الرقبة",
              "عرض الظهر", "عرض الصدر"],
    "بنطلون": ["الطول", "الوسط", "الهانش", "الفخذ", "الركبة", "فتحة الرجل", "الحِجر"],
    "صديرى": ["الطول", "الصدر", "الوسط"],
}

DEFAULT_STYLE_OPTIONS = [
    ("الياقة", "عادية\nشال\nمدببة (Peak)"),
    ("الزراير", "زرار واحد\n2 زرار\n3 زراير\nدبل (صفين)"),
    ("الفتحة من ورا", "بدون\nفتحة واحدة\nفتحتين"),
    ("الجيوب", "عادى بقلاب\nمن غير قلاب\nجيب ساعة"),
    ("البطانة", "كاملة\nنص بطانة"),
    ("البنطلون", "بكسرة\nمن غير كسرة"),
]
