-- =====================================================================
--  01_tables.sql — الجداول
--  شغّله الأول فى Supabase: SQL Editor ← New query ← الصق ← Run
--
--  الفكرة: كل جدول فيه company_id، وكل شركة مش بتشوف غير بياناتها
--  (ده بيتظبط فى 02_security.sql).
-- =====================================================================

-- ========================= الشركات والمستخدمين =========================

create table if not exists public.companies (
    id                uuid primary key default gen_random_uuid(),
    name              text not null check (length(btrim(name)) > 0),
    logo_path         text,
    -- حساب الربح بيبدأ من التاريخ ده (فى وينتاج كان ثابت على 1/8/2026)
    profit_start_date date,
    -- لازم فاتورة PDF مع كل تعاقد؟
    require_invoice   boolean not null default true,
    -- كود بيدّيه المدير للموظفين عشان ينضموا للشركة
    join_code         text not null unique default upper(substr(md5(gen_random_uuid()::text), 1, 8)),
    created_at        timestamptz not null default now()
);

create table if not exists public.branches (
    id          uuid primary key default gen_random_uuid(),
    company_id  uuid not null references public.companies on delete cascade,
    name        text not null check (length(btrim(name)) > 0),
    is_main     boolean not null default false,
    created_at  timestamptz not null default now(),
    unique (company_id, name)
);

-- كل مستخدم (من Supabase Auth) تبع شركة واحدة
-- الصفحات: dashboard, treasury, suppliers, cheques, sales, inspections,
--          factory, install, accounts, staff, settings
create table if not exists public.profiles (
    user_id       uuid primary key references auth.users on delete cascade,
    company_id    uuid not null references public.companies on delete cascade,
    full_name     text not null check (length(btrim(full_name)) > 0),
    role_title    text,
    is_active     boolean not null default false,   -- المدير بيفعّله
    is_admin      boolean not null default false,   -- المدير بيشوف ويعمل كل حاجة
    pages         text[] not null default '{}',     -- يشوف
    edit_pages    text[] not null default '{}',     -- يضيف/يعدّل
    delete_pages  text[] not null default '{}',     -- يمسح
    created_at    timestamptz not null default now()
);

-- ========================= إعدادات كل شركة =========================

create table if not exists public.payment_methods (
    id          uuid primary key default gen_random_uuid(),
    company_id  uuid not null references public.companies on delete cascade,
    name        text not null,
    -- نوع القناة: بيستخدم فى "توزيع الفلوس" وفى اختيار الطريقة أوتوماتيك
    channel     text not null check (channel in ('cash', 'bank', 'wallet', 'cheque')),
    sort        int not null default 0,
    is_active   boolean not null default true,
    unique (company_id, name)
);

create table if not exists public.product_types (
    id               uuid primary key default gen_random_uuid(),
    company_id       uuid not null references public.companies on delete cascade,
    name             text not null,
    for_contracts    boolean not null default true,
    for_maintenance  boolean not null default true,
    sort             int not null default 0,
    is_active        boolean not null default true,
    unique (company_id, name)
);

-- الإدارات: بدل "الكلمات الدالة" فى وينتاج، كل إدارة عليها علامة صريحة
create table if not exists public.departments (
    id          uuid primary key default gen_random_uuid(),
    company_id  uuid not null references public.companies on delete cascade,
    name        text not null,
    is_sales    boolean not null default false,  -- الوارد بإدارة دى = مبيعات (فى الربح)
    in_profit   boolean not null default false,  -- المنصرف بإدارة دى = تكلفة (فى الربح)
    sort        int not null default 0,
    is_active   boolean not null default true,
    unique (company_id, name)
);

-- السيلز والصنايعية (مش لازم يكونوا مستخدمين للبرنامج)
create table if not exists public.staff (
    id          uuid primary key default gen_random_uuid(),
    company_id  uuid not null references public.companies on delete cascade,
    name        text not null check (length(btrim(name)) > 0),
    mobile      text,
    kind        text not null default 'sales' check (kind in ('sales', 'craftsman', 'other')),
    hired_on    date,
    is_active   boolean not null default true,
    created_at  timestamptz not null default now(),
    unique (company_id, name, kind)
);

create table if not exists public.customers (
    id          uuid primary key default gen_random_uuid(),
    company_id  uuid not null references public.companies on delete cascade,
    name        text not null check (length(btrim(name)) > 0),
    mobile      text,
    address     text,
    created_at  timestamptz not null default now()
);
create index if not exists customers_company_mobile on public.customers (company_id, mobile);

-- ========================= الموردين =========================

create table if not exists public.suppliers (
    id             uuid primary key default gen_random_uuid(),
    company_id     uuid not null references public.companies on delete cascade,
    name           text not null check (length(btrim(name)) > 0),
    material       text,
    mobile         text,
    supplier_type  text,
    created_at     timestamptz not null default now(),
    unique (company_id, name)
);

-- ========================= العمليات (تعاقدات + صيانة) =========================
-- فى وينتاج العملية المكتملة كانت بتتمسح من التعاقدات وتتنقل لشيت المبيعات.
-- هنا بتفضل فى نفس الجدول وحالتها بتبقى completed - مفيش نقل ولا مسح.

create table if not exists public.jobs (
    id                         bigint generated always as identity primary key,
    company_id                 uuid not null references public.companies on delete cascade,
    branch_id                  uuid not null references public.branches,
    kind                       text not null check (kind in ('contract', 'maintenance')),
    customer_id                uuid not null references public.customers,
    place                      text,
    product_type_id            uuid references public.product_types,
    meters                     numeric(10, 2) not null default 0 check (meters >= 0),
    price                      numeric(14, 2) not null check (price > 0),
    advance                    numeric(14, 2) not null default 0 check (advance >= 0),
    advance_method_id          uuid references public.payment_methods,
    seller_id                  uuid references public.staff,
    invoice_paths              text[] not null default '{}',
    description                text,
    note                       text,
    status                     text not null check (status in
        ('awaiting_advance', 'manufacturing', 'installing', 'awaiting_accounts', 'completed')),
    craftsman                  text,
    final_collected            numeric(14, 2) check (final_collected >= 0),
    final_method_id            uuid references public.payment_methods,
    created_by                 uuid default auth.uid(),
    created_at                 timestamptz not null default now(),
    manufacturing_started_at   timestamptz,
    installing_started_at      timestamptz,
    install_finished_at        timestamptz,
    completed_at               timestamptz,
    completed_by               uuid
);
create index if not exists jobs_company_status on public.jobs (company_id, status);

create table if not exists public.inspections (
    id               bigint generated always as identity primary key,
    company_id       uuid not null references public.companies on delete cascade,
    branch_id        uuid not null references public.branches,
    customer_id      uuid not null references public.customers,
    place            text not null,
    product_type_id  uuid references public.product_types,
    notes            text,
    status           text not null default 'active' check (status in ('active', 'done')),
    created_by       uuid default auth.uid(),
    created_at       timestamptz not null default now(),
    closed_at        timestamptz
);
create index if not exists inspections_company_status on public.inspections (company_id, status);

-- ========================= الخزينة =========================

create table if not exists public.treasury_entries (
    id                 bigint generated always as identity primary key,
    company_id         uuid not null references public.companies on delete cascade,
    branch_id          uuid not null references public.branches,
    entry_date         date not null default current_date,
    amount_in          numeric(14, 2) not null default 0 check (amount_in >= 0),
    amount_out         numeric(14, 2) not null default 0 check (amount_out >= 0),
    description        text not null check (length(btrim(description)) > 0),
    payment_method_id  uuid references public.payment_methods,
    department_id      uuid references public.departments,
    counterparty       text,
    supplier_id        uuid references public.suppliers,
    job_id             bigint references public.jobs,
    source             text not null default 'manual' check (source in
        ('manual', 'supplier_payment', 'cheque', 'job_advance', 'job_final')),
    created_by         uuid default auth.uid(),
    created_at         timestamptz not null default now(),
    -- لازم جنب واحد بس: يا وارد يا منصرف
    check ((amount_in > 0) <> (amount_out > 0))
);
create index if not exists treasury_company_date on public.treasury_entries (company_id, entry_date);

create table if not exists public.supplier_txns (
    id                 bigint generated always as identity primary key,
    company_id         uuid not null references public.companies on delete cascade,
    supplier_id        uuid not null references public.suppliers on delete cascade,
    txn_date           date not null default current_date,
    txn_type           text not null check (txn_type in
        ('invoice', 'cash_payment', 'bank_payment', 'cheque', 'return')),
    description        text,
    amount             numeric(14, 2) not null check (amount > 0),
    cheque_no          text,
    due_date           date,
    cheque_status      text check (cheque_status in ('due', 'cashed')),
    -- لو القيد اتمسح من الخزينة، الحركة المرتبطة بيه تتمسح معاه (زى وينتاج)
    treasury_entry_id  bigint references public.treasury_entries on delete cascade,
    created_by         uuid default auth.uid(),
    created_at         timestamptz not null default now(),
    check (txn_type <> 'cheque' or (due_date is not null and cheque_status is not null))
);
create index if not exists supplier_txns_company_supplier on public.supplier_txns (company_id, supplier_id);

-- ========================= سجل النشاط =========================

create table if not exists public.activity_log (
    id          bigint generated always as identity primary key,
    company_id  uuid not null references public.companies on delete cascade,
    user_id     uuid default auth.uid(),
    action      text not null,
    details     text,
    amount      numeric(14, 2),
    created_at  timestamptz not null default now()
);
create index if not exists activity_company_time on public.activity_log (company_id, created_at desc);
