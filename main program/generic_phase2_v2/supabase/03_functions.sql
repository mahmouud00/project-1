-- =====================================================================
--  03_functions.sql — كل العمليات
--
--  كل عملية = دالة بتتنفذ على السيرفر:
--   - بتفحص الصلاحية
--   - بتنفذ كل الخطوات مع بعض (لو خطوة فشلت، ولا حاجة بتتسجل)
--   - بتقفل الصف وهى شغالة عليه، فلو اتنين داسوا "تأكيد" فى نفس اللحظة
--     التانى هيلاقى الحالة اتغيرت ويترفض (مفيش فلوس بتترحّل مرتين)
--  البرنامج بينادى الدوال دى بـ supabase.rpc("اسم_الدالة", {...})
-- =====================================================================

-- ========================= دوال داخلية =========================

create or replace function public._require(p_page text, p_action text)
returns uuid language plpgsql stable security definer set search_path = public as $$
declare v_company uuid;
begin
    v_company := public.my_company_id();
    if v_company is null then
        raise exception 'حسابك مش متفعّل فى أى شركة — كلّم مدير الشركة';
    end if;
    if not public.can_do(p_page, p_action) then
        raise exception 'مفيش صلاحية لك تعمل العملية دى';
    end if;
    return v_company;
end $$;

create or replace function public._log(p_company uuid, p_action text, p_details text, p_amount numeric default null)
returns void language sql security definer set search_path = public as $$
    insert into public.activity_log (company_id, action, details, amount)
    values (p_company, p_action, p_details, nullif(p_amount, 0))
$$;

-- الفرع: لو مش محدد يبقى الفرع الرئيسى
create or replace function public._branch(p_company uuid, p_branch uuid)
returns uuid language plpgsql stable security definer set search_path = public as $$
declare v uuid;
begin
    if p_branch is null then
        select id into v from public.branches where company_id = p_company and is_main limit 1;
    else
        select id into v from public.branches where company_id = p_company and id = p_branch;
    end if;
    if v is null then raise exception 'الفرع غير صحيح'; end if;
    return v;
end $$;

-- بيتأكد إن الحاجة المختارة (طريقة دفع، إدارة...) تبع نفس الشركة
create or replace function public._check_owned(p_table text, p_id uuid, p_company uuid, p_label text)
returns void language plpgsql stable security definer set search_path = public as $$
declare ok boolean;
begin
    if p_id is null then return; end if;
    execute format('select exists (select 1 from public.%I where id = $1 and company_id = $2)', p_table)
        into ok using p_id, p_company;
    if not ok then raise exception '% غير صحيح', p_label; end if;
end $$;

-- بيجيب العميل بالموبايل، ولو مش موجود بيضيفه
create or replace function public._customer(p_company uuid, p_name text, p_mobile text)
returns uuid language plpgsql security definer set search_path = public as $$
declare
    v uuid;
    n text := btrim(coalesce(p_name, ''));
    m text := nullif(btrim(coalesce(p_mobile, '')), '');
begin
    if n = '' then raise exception 'اسم العميل مطلوب'; end if;
    if m is not null then
        select id into v from public.customers where company_id = p_company and mobile = m limit 1;
    end if;
    if v is null then
        insert into public.customers (company_id, name, mobile) values (p_company, n, m) returning id into v;
    end if;
    return v;
end $$;

create or replace function public._method_by_channel(p_company uuid, p_channel text)
returns uuid language sql stable security definer set search_path = public as $$
    select id from public.payment_methods
    where company_id = p_company and channel = p_channel and is_active
    order by sort, name limit 1
$$;

create or replace function public._sales_department(p_company uuid)
returns uuid language sql stable security definer set search_path = public as $$
    select id from public.departments
    where company_id = p_company and is_sales and is_active
    order by sort, name limit 1
$$;

create or replace function public._treasury_insert(
    p_company uuid, p_branch uuid, p_amount_in numeric, p_amount_out numeric, p_description text,
    p_method uuid, p_department uuid, p_date date, p_counterparty text,
    p_supplier uuid, p_job bigint, p_source text)
returns bigint language plpgsql security definer set search_path = public as $$
declare v bigint;
begin
    insert into public.treasury_entries (company_id, branch_id, entry_date, amount_in, amount_out, description,
        payment_method_id, department_id, counterparty, supplier_id, job_id, source)
    values (p_company, p_branch, coalesce(p_date, current_date), coalesce(p_amount_in, 0), coalesce(p_amount_out, 0),
        p_description, p_method, p_department, p_counterparty, p_supplier, p_job, p_source)
    returning id into v;
    return v;
end $$;

-- ========================= الشركة والموظفين =========================

-- أول مستخدم بيعمل الشركة وبيبقى مديرها، ومعاها إعدادات افتراضية يعدّلها بعدين
create or replace function public.create_company(p_company_name text, p_full_name text)
returns uuid language plpgsql security definer set search_path = public as $$
declare v_company uuid;
begin
    if auth.uid() is null then raise exception 'لازم تسجل دخول الأول'; end if;
    if exists (select 1 from public.profiles where user_id = auth.uid()) then
        raise exception 'حسابك تبع شركة بالفعل';
    end if;
    if length(btrim(coalesce(p_company_name, ''))) = 0 then raise exception 'اسم الشركة مطلوب'; end if;

    insert into public.companies (name) values (btrim(p_company_name)) returning id into v_company;
    insert into public.branches (company_id, name, is_main) values (v_company, 'الفرع الرئيسى', true);
    insert into public.profiles (user_id, company_id, full_name, role_title, is_active, is_admin)
    values (auth.uid(), v_company, coalesce(nullif(btrim(p_full_name), ''), 'المدير'), 'مدير', true, true);

    insert into public.payment_methods (company_id, name, channel, sort) values
        (v_company, 'نقدى', 'cash', 1), (v_company, 'بنك', 'bank', 2), (v_company, 'انستاباى', 'wallet', 3),
        (v_company, 'فودافون كاش', 'wallet', 4), (v_company, 'شيك', 'cheque', 5);
    insert into public.product_types (company_id, name, for_contracts, for_maintenance, sort) values
        (v_company, 'شاتر', true, true, 1), (v_company, 'UPVC', true, true, 2),
        (v_company, 'شاتر + UPVC', true, false, 3), (v_company, 'مشروع خاص', true, false, 4),
        (v_company, 'عزل', false, true, 5), (v_company, 'أخرى', true, true, 6);
    insert into public.departments (company_id, name, is_sales, in_profit, sort) values
        (v_company, 'مبيعات', true, true, 1), (v_company, 'المشتريات', false, true, 2),
        (v_company, 'التصنيع', false, true, 3), (v_company, 'التركيبات', false, true, 4),
        (v_company, 'المعاينات', false, true, 5), (v_company, 'إدارية', false, false, 6);

    perform public._log(v_company, 'إنشاء الشركة', p_company_name);
    return v_company;
end $$;

-- الموظف بيعمل حساب، وبيكتب كود الشركة اللى المدير إداهوله. بيفضل موقوف لحد ما المدير يفعّله.
create or replace function public.join_company(p_join_code text, p_full_name text)
returns uuid language plpgsql security definer set search_path = public as $$
declare v_company uuid;
begin
    if auth.uid() is null then raise exception 'لازم تسجل دخول الأول'; end if;
    if exists (select 1 from public.profiles where user_id = auth.uid()) then
        raise exception 'حسابك تبع شركة بالفعل';
    end if;
    select id into v_company from public.companies where join_code = upper(btrim(p_join_code));
    if v_company is null then raise exception 'كود الشركة غلط'; end if;
    if length(btrim(coalesce(p_full_name, ''))) = 0 then raise exception 'اكتب اسمك'; end if;
    insert into public.profiles (user_id, company_id, full_name) values (auth.uid(), v_company, btrim(p_full_name));
    perform public._log(v_company, 'طلب انضمام', p_full_name);
    return v_company;
end $$;

-- المدير بيفعّل الموظف ويحدد صلاحياته
create or replace function public.set_member(p_user_id uuid, p_is_active boolean, p_is_admin boolean,
    p_pages text[], p_edit_pages text[], p_delete_pages text[], p_role_title text default null)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public.my_company_id();
begin
    if not public.is_company_admin() then raise exception 'المدير بس يقدر يعدّل الموظفين'; end if;
    if p_user_id = auth.uid() and (not p_is_admin or not p_is_active) then
        raise exception 'مينفعش تشيل صلاحية المدير من نفسك';
    end if;
    update public.profiles set is_active = p_is_active, is_admin = p_is_admin,
        pages = coalesce(p_pages, '{}'), edit_pages = coalesce(p_edit_pages, '{}'),
        delete_pages = coalesce(p_delete_pages, '{}'), role_title = coalesce(p_role_title, role_title)
    where user_id = p_user_id and company_id = v_company;
    if not found then raise exception 'الموظف ده مش تبع شركتك'; end if;
    perform public._log(v_company, 'تعديل صلاحيات موظف', p_user_id::text);
end $$;

create or replace function public.add_staff(p_name text, p_mobile text default null,
    p_kind text default 'sales', p_hired_on date default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('staff', 'edit'); v uuid;
begin
    if length(btrim(coalesce(p_name, ''))) = 0 then raise exception 'اسم الموظف مطلوب'; end if;
    if exists (select 1 from public.staff where company_id = v_company and name = btrim(p_name)
               and kind = coalesce(p_kind, 'sales')) then
        raise exception 'الموظف ده موجود بالفعل';
    end if;
    insert into public.staff (company_id, name, mobile, kind, hired_on)
    values (v_company, btrim(p_name), nullif(btrim(coalesce(p_mobile, '')), ''), coalesce(p_kind, 'sales'),
            coalesce(p_hired_on, current_date))
    returning id into v;
    perform public._log(v_company, 'إضافة موظف', p_name);
    return v;
end $$;

-- ========================= الخزينة =========================

create or replace function public.add_treasury_entry(p_direction text, p_amount numeric, p_description text,
    p_payment_method_id uuid default null, p_department_id uuid default null, p_entry_date date default null,
    p_branch_id uuid default null, p_counterparty text default null)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('treasury', 'edit');
    v_branch uuid;
    v bigint;
begin
    if p_direction not in ('in', 'out') then raise exception 'اختار وارد أو منصرف'; end if;
    if p_amount is null or p_amount <= 0 then raise exception 'المبلغ مطلوب ولازم يكون أكبر من صفر'; end if;
    if length(btrim(coalesce(p_description, ''))) = 0 then raise exception 'وصف القيد مطلوب'; end if;
    v_branch := public._branch(v_company, p_branch_id);
    perform public._check_owned('payment_methods', p_payment_method_id, v_company, 'طريقة الدفع');
    perform public._check_owned('departments', p_department_id, v_company, 'الإدارة');

    v := public._treasury_insert(v_company, v_branch,
        case when p_direction = 'in' then p_amount end, case when p_direction = 'out' then p_amount end,
        btrim(p_description), p_payment_method_id, p_department_id, p_entry_date,
        nullif(btrim(coalesce(p_counterparty, '')), ''), null, null, 'manual');
    perform public._log(v_company, 'قيد خزينة', p_description, p_amount);
    return v;
end $$;

create or replace function public.update_treasury_department(p_entry_id bigint, p_department_id uuid)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('treasury', 'edit');
begin
    perform public._check_owned('departments', p_department_id, v_company, 'الإدارة');
    update public.treasury_entries set department_id = p_department_id
    where id = p_entry_id and company_id = v_company;
    if not found then raise exception 'القيد ده مش موجود'; end if;
    perform public._log(v_company, 'تعديل إدارة قيد', p_entry_id::text);
end $$;

-- بيرجّع عدد حركات الموردين اللى اتمسحت معاه
create or replace function public.delete_treasury_entry(p_entry_id bigint)
returns int language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('treasury', 'delete');
    r public.treasury_entries;
    v_linked int;
begin
    select * into r from public.treasury_entries where id = p_entry_id and company_id = v_company for update;
    if not found then raise exception 'القيد ده مش موجود'; end if;
    if r.source in ('job_advance', 'job_final') then
        raise exception 'القيد ده جاى من تحصيل عملية (%). عدّل العملية نفسها بدل ما تمسح القيد', r.job_id;
    end if;
    select count(*) into v_linked from public.supplier_txns where treasury_entry_id = p_entry_id;
    delete from public.treasury_entries where id = p_entry_id;   -- حركة المورد بتتمسح معاه (cascade)
    perform public._log(v_company, 'مسح قيد خزينة', r.description, r.amount_in + r.amount_out);
    return v_linked;
end $$;

-- ========================= الموردين والشيكات =========================

create or replace function public.add_supplier(p_name text, p_material text default null,
    p_mobile text default null, p_supplier_type text default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('suppliers', 'edit'); v uuid;
begin
    if length(btrim(coalesce(p_name, ''))) = 0 then raise exception 'اسم المورد مطلوب'; end if;
    if exists (select 1 from public.suppliers where company_id = v_company and name = btrim(p_name)) then
        raise exception 'المورد "%" موجود بالفعل', btrim(p_name);
    end if;
    insert into public.suppliers (company_id, name, material, mobile, supplier_type)
    values (v_company, btrim(p_name), nullif(btrim(coalesce(p_material, '')), ''),
            nullif(btrim(coalesce(p_mobile, '')), ''), coalesce(p_supplier_type, 'أخرى'))
    returning id into v;
    perform public._log(v_company, 'إضافة مورد', p_name);
    return v;
end $$;

-- الدفعات النقدية/البنكية بتنزل فى الخزينة أوتوماتيك
create or replace function public.add_supplier_txn(p_supplier_id uuid, p_txn_type text, p_amount numeric,
    p_description text default null, p_cheque_no text default null, p_due_date date default null,
    p_branch_id uuid default null)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('suppliers', 'edit');
    v_supplier public.suppliers;
    v_treasury bigint;
    v_method uuid;
    v bigint;
begin
    select * into v_supplier from public.suppliers where id = p_supplier_id and company_id = v_company;
    if not found then raise exception 'اختار المورد'; end if;
    if p_txn_type not in ('invoice', 'cash_payment', 'bank_payment', 'cheque', 'return') then
        raise exception 'اختار نوع الحركة';
    end if;
    if p_amount is null or p_amount <= 0 then raise exception 'المبلغ مطلوب ولازم يكون أكبر من صفر'; end if;
    if p_txn_type = 'cheque' and p_due_date is null then raise exception 'تاريخ استحقاق الشيك مطلوب'; end if;

    if p_txn_type in ('cash_payment', 'bank_payment') then
        v_method := public._method_by_channel(v_company, case when p_txn_type = 'cash_payment' then 'cash' else 'bank' end);
        v_treasury := public._treasury_insert(v_company, public._branch(v_company, p_branch_id), null, p_amount,
            coalesce(nullif(btrim(coalesce(p_description, '')), ''), 'دفعة لمورد ' || v_supplier.name),
            v_method, null, current_date, v_supplier.name, v_supplier.id, null, 'supplier_payment');
    end if;

    insert into public.supplier_txns (company_id, supplier_id, txn_type, description, amount,
        cheque_no, due_date, cheque_status, treasury_entry_id)
    values (v_company, v_supplier.id, p_txn_type, nullif(btrim(coalesce(p_description, '')), ''), p_amount,
        case when p_txn_type = 'cheque' then nullif(btrim(coalesce(p_cheque_no, '')), '') end,
        case when p_txn_type = 'cheque' then p_due_date end,
        case when p_txn_type = 'cheque' then 'due' end,
        v_treasury)
    returning id into v;
    perform public._log(v_company, 'حركة مورد: ' || p_txn_type, v_supplier.name, p_amount);
    return v;
end $$;

-- كل شيك جه ميعاده (النهارده أو فات) ← قيد منصرف فى الخزينة + يتعلّم "اتصرف"
create or replace function public.cash_due_cheques(p_branch_id uuid default null)
returns int language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('cheques', 'edit');
    v_branch uuid;
    v_method uuid;
    c record;
    v_treasury bigint;
    n int := 0;
begin
    v_branch := public._branch(v_company, p_branch_id);
    v_method := public._method_by_channel(v_company, 'cheque');
    for c in
        select t.id, t.amount, t.cheque_no, t.due_date, s.id as supplier_id, s.name as supplier_name
        from public.supplier_txns t join public.suppliers s on s.id = t.supplier_id
        where t.company_id = v_company and t.txn_type = 'cheque' and t.cheque_status = 'due'
              and t.due_date <= current_date
        order by t.due_date
        for update of t
    loop
        v_treasury := public._treasury_insert(v_company, v_branch, null, c.amount,
            'صرف شيك رقم ' || coalesce(c.cheque_no, '—') || ' - ' || c.supplier_name,
            v_method, null, c.due_date, c.supplier_name, c.supplier_id, null, 'cheque');
        update public.supplier_txns set cheque_status = 'cashed', treasury_entry_id = v_treasury where id = c.id;
        n := n + 1;
    end loop;
    if n > 0 then perform public._log(v_company, 'ترحيل شيكات مستحقة', n || ' شيك'); end if;
    return n;
end $$;

-- ========================= المعاينات =========================

create or replace function public.add_inspection(p_customer_name text, p_mobile text, p_place text,
    p_product_type_id uuid default null, p_notes text default null, p_branch_id uuid default null)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public.my_company_id();
    v bigint;
begin
    if not (public.can_do('sales', 'edit') or public.can_do('inspections', 'edit')) then
        raise exception 'مفيش صلاحية لك تعمل العملية دى';
    end if;
    if nullif(btrim(coalesce(p_mobile, '')), '') is null then raise exception 'رقم الموبايل مطلوب'; end if;
    if nullif(btrim(coalesce(p_place, '')), '') is null then raise exception 'المكان مطلوب'; end if;
    perform public._check_owned('product_types', p_product_type_id, v_company, 'النوع');
    insert into public.inspections (company_id, branch_id, customer_id, place, product_type_id, notes)
    values (v_company, public._branch(v_company, p_branch_id), public._customer(v_company, p_customer_name, p_mobile),
            btrim(p_place), p_product_type_id, nullif(btrim(coalesce(p_notes, '')), ''))
    returning id into v;
    perform public._log(v_company, 'طلب معاينة', p_customer_name);
    return v;
end $$;

create or replace function public.close_inspection(p_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('inspections', 'edit');
begin
    update public.inspections set status = 'done', closed_at = now()
    where id = p_id and company_id = v_company and status = 'active';
    if not found then raise exception 'المعاينة دى مش موجودة أو متقفلة بالفعل'; end if;
    perform public._log(v_company, 'إقفال معاينة', p_id::text);
end $$;

create or replace function public.update_inspection(p_id bigint, p_place text, p_notes text)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('inspections', 'edit');
begin
    update public.inspections
    set place = coalesce(nullif(btrim(coalesce(p_place, '')), ''), place),
        notes = nullif(btrim(coalesce(p_notes, '')), '')
    where id = p_id and company_id = v_company;
    if not found then raise exception 'المعاينة دى مش موجودة'; end if;
    perform public._log(v_company, 'تعديل معاينة', p_id::text);
end $$;

create or replace function public.delete_inspection(p_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('inspections', 'delete');
begin
    delete from public.inspections where id = p_id and company_id = v_company;
    if not found then raise exception 'المعاينة دى مش موجودة'; end if;
    perform public._log(v_company, 'مسح معاينة', p_id::text);
end $$;

-- ========================= العمليات: تعاقد وصيانة =========================

-- الصفحة المسئولة عن كل مرحلة (للصلاحيات)
create or replace function public._stage_page(p_status text)
returns text language sql immutable as $$
    select case p_status
        when 'manufacturing' then 'factory'
        when 'installing' then 'install'
        else 'accounts' end
$$;

create or replace function public.add_job(p_kind text, p_customer_name text, p_mobile text, p_place text,
    p_product_type_id uuid, p_price numeric, p_meters numeric default 0, p_advance numeric default 0,
    p_advance_method_id uuid default null, p_seller_id uuid default null,
    p_invoice_paths text[] default '{}', p_description text default null, p_branch_id uuid default null)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('sales', 'edit');
    v_require_invoice boolean;
    v bigint;
begin
    if p_kind not in ('contract', 'maintenance') then raise exception 'نوع العملية غير صحيح'; end if;
    if p_price is null or p_price <= 0 then raise exception 'السعر مطلوب'; end if;
    perform public._check_owned('product_types', p_product_type_id, v_company, 'النوع');
    perform public._check_owned('payment_methods', p_advance_method_id, v_company, 'طريقة دفع المقدم');
    perform public._check_owned('staff', p_seller_id, v_company, 'السيلز');

    if p_kind = 'contract' then
        if nullif(btrim(coalesce(p_mobile, '')), '') is null then raise exception 'رقم الموبايل مطلوب'; end if;
        if nullif(btrim(coalesce(p_place, '')), '') is null then raise exception 'المكان مطلوب'; end if;
        if coalesce(p_meters, 0) <= 0 then raise exception 'عدد الأمتار مطلوب'; end if;
        if coalesce(p_advance, 0) < 0 or coalesce(p_advance, 0) > p_price then
            raise exception 'المقدم لازم يكون بين صفر والسعر الإجمالى';
        end if;
        if coalesce(p_advance, 0) > 0 and p_advance_method_id is null then
            raise exception 'اختار طريقة دفع المقدم';
        end if;
        select require_invoice into v_require_invoice from public.companies where id = v_company;
        if v_require_invoice and coalesce(array_length(p_invoice_paths, 1), 0) = 0 then
            raise exception 'لازم ترفع فاتورة واحدة على الأقل PDF';
        end if;
    end if;

    insert into public.jobs (company_id, branch_id, kind, customer_id, place, product_type_id, meters, price,
        advance, advance_method_id, seller_id, invoice_paths, description, status, installing_started_at)
    values (v_company, public._branch(v_company, p_branch_id), p_kind,
        public._customer(v_company, p_customer_name, p_mobile), nullif(btrim(coalesce(p_place, '')), ''),
        p_product_type_id, coalesce(p_meters, 0), p_price,
        case when p_kind = 'contract' then coalesce(p_advance, 0) else 0 end,
        case when p_kind = 'contract' then p_advance_method_id end,
        p_seller_id, coalesce(p_invoice_paths, '{}'), nullif(btrim(coalesce(p_description, '')), ''),
        -- الصيانة بتدخل التركيبات على طول
        case when p_kind = 'contract' then 'awaiting_advance' else 'installing' end,
        case when p_kind = 'maintenance' then now() end)
    returning id into v;
    perform public._log(v_company, case when p_kind = 'contract' then 'إضافة تعاقد' else 'طلب صيانة' end,
                        p_customer_name, p_price);
    return v;
end $$;

-- 1) الحسابات تأكد المقدم ← يترحّل للخزينة ← العملية تدخل التصنيع
create or replace function public.confirm_advance(p_job_id bigint)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('accounts', 'edit');
    j public.jobs;
    v_name text;
    v_treasury bigint;
begin
    select * into j from public.jobs where id = p_job_id and company_id = v_company for update;
    if not found then raise exception 'العملية دى مش موجودة'; end if;
    if j.status <> 'awaiting_advance' then raise exception 'العملية دى مش فى انتظار تأكيد المقدم'; end if;
    select name into v_name from public.customers where id = j.customer_id;
    if j.advance > 0 then
        v_treasury := public._treasury_insert(v_company, j.branch_id, j.advance, null,
            'مقدم تعاقد من العميل ' || v_name, j.advance_method_id, public._sales_department(v_company),
            current_date, v_name, null, j.id, 'job_advance');
    end if;
    update public.jobs set status = 'manufacturing', manufacturing_started_at = now() where id = j.id;
    perform public._log(v_company, 'تأكيد مقدم وترحيل للتصنيع', v_name, j.advance);
    return v_treasury;
end $$;

-- 2) المصنع خلّص ← التركيبات
create or replace function public.finish_manufacturing(p_job_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('factory', 'edit');
begin
    update public.jobs set status = 'installing', installing_started_at = now()
    where id = p_job_id and company_id = v_company and status = 'manufacturing';
    if not found then raise exception 'العملية دى مش فى مرحلة التصنيع'; end if;
    perform public._log(v_company, 'ترحيل من تصنيع لتركيب', p_job_id::text);
end $$;

-- 3) التركيب خلّص + المحصّل من العميل ← تأكيد الحسابات
create or replace function public.finish_installation(p_job_id bigint, p_collected numeric,
    p_method_id uuid, p_craftsman text)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public._require('install', 'edit');
begin
    if p_collected is null or p_collected < 0 then raise exception 'لازم تكتب المبلغ المحصّل من العميل'; end if;
    if p_method_id is null then raise exception 'اختار طريقة الدفع'; end if;
    if nullif(btrim(coalesce(p_craftsman, '')), '') is null then raise exception 'اكتب اسم الصنايعى'; end if;
    perform public._check_owned('payment_methods', p_method_id, v_company, 'طريقة الدفع');
    update public.jobs set status = 'awaiting_accounts', final_collected = p_collected,
        final_method_id = p_method_id, craftsman = btrim(p_craftsman), install_finished_at = now()
    where id = p_job_id and company_id = v_company and status = 'installing';
    if not found then raise exception 'العملية دى مش فى مرحلة التركيب'; end if;
    perform public._log(v_company, 'تم التركيب — فى انتظار تأكيد الحسابات', p_job_id::text, p_collected);
end $$;

-- 4) التأكيد النهائى ← المحصّل يترحّل للخزينة ← العملية "مكتملة"
create or replace function public.confirm_final(p_job_id bigint)
returns bigint language plpgsql security definer set search_path = public as $$
declare
    v_company uuid := public._require('accounts', 'edit');
    j public.jobs;
    v_name text;
    v_treasury bigint;
begin
    select * into j from public.jobs where id = p_job_id and company_id = v_company for update;
    if not found then raise exception 'العملية دى مش موجودة'; end if;
    if j.status <> 'awaiting_accounts' then raise exception 'العملية دى لسه مش وصلت لمرحلة تأكيد الحسابات'; end if;
    select name into v_name from public.customers where id = j.customer_id;
    if coalesce(j.final_collected, 0) > 0 then
        v_treasury := public._treasury_insert(v_company, j.branch_id, j.final_collected, null,
            'تحصيل من العميل ' || v_name || ' بعد التسليم', j.final_method_id, public._sales_department(v_company),
            current_date, v_name, null, j.id, 'job_final');
    end if;
    update public.jobs set status = 'completed', completed_at = now(), completed_by = auth.uid() where id = j.id;
    perform public._log(v_company, 'تأكيد الحسابات النهائى', v_name, j.final_collected);
    return v_treasury;
end $$;

-- تعديل: المقدم بيتعدّل بس قبل تأكيده (عشان الخزينة متبقاش مختلفة عن العملية)
create or replace function public.update_job(p_job_id bigint, p_place text default null,
    p_price numeric default null, p_advance numeric default null, p_meters numeric default null)
returns void language plpgsql security definer set search_path = public as $$
declare
    j public.jobs;
    v_company uuid := public.my_company_id();
    v_price numeric;
    v_advance numeric;
begin
    select * into j from public.jobs where id = p_job_id and company_id = v_company for update;
    if not found then raise exception 'العملية دى مش موجودة'; end if;
    if j.status = 'completed' then raise exception 'العملية دى مكتملة ومينفعش تتعدّل'; end if;
    perform public._require(public._stage_page(j.status), 'edit');
    if p_advance is not null and p_advance <> j.advance and j.status <> 'awaiting_advance' then
        raise exception 'المقدم اتأكد واترحّل للخزينة خلاص، ومينفعش يتعدّل';
    end if;
    v_price := coalesce(p_price, j.price);
    v_advance := coalesce(p_advance, j.advance);
    if v_price <= 0 then raise exception 'السعر لازم يكون أكبر من صفر'; end if;
    if v_advance < 0 or v_advance > v_price then raise exception 'المقدم لازم يكون بين صفر والسعر الإجمالى'; end if;
    update public.jobs set place = coalesce(nullif(btrim(coalesce(p_place, '')), ''), place),
        price = v_price, advance = v_advance, meters = coalesce(p_meters, meters)
    where id = j.id;
    perform public._log(v_company, 'تعديل عملية', p_job_id::text);
end $$;

create or replace function public.set_job_note(p_job_id bigint, p_note text)
returns void language plpgsql security definer set search_path = public as $$
declare j public.jobs; v_company uuid := public.my_company_id();
begin
    select * into j from public.jobs where id = p_job_id and company_id = v_company;
    if not found then raise exception 'العملية دى مش موجودة'; end if;
    perform public._require(public._stage_page(j.status), 'edit');
    update public.jobs set note = nullif(btrim(coalesce(p_note, '')), '') where id = j.id;
    perform public._log(v_company, 'ملاحظة على عملية', p_note);
end $$;

-- المسح مسموح بس قبل ما أى فلوس تترحّل للخزينة
create or replace function public.delete_job(p_job_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare j public.jobs; v_company uuid := public.my_company_id();
begin
    select * into j from public.jobs where id = p_job_id and company_id = v_company for update;
    if not found then raise exception 'العملية دى مش موجودة'; end if;
    perform public._require(public._stage_page(j.status), 'delete');
    if exists (select 1 from public.treasury_entries where job_id = j.id) then
        raise exception 'العملية دى ليها فلوس مترحّلة للخزينة ومينفعش تتمسح';
    end if;
    delete from public.jobs where id = j.id;
    perform public._log(v_company, 'مسح عملية', p_job_id::text, j.price);
end $$;

-- ========================= الصلاحيات على الدوال =========================
-- الدوال الداخلية (اللى بتبدأ بـ _) محدش يناديها من برا، والباقى للمستخدمين المسجلين بس.
do $$
declare f record;
begin
    for f in
        select p.oid::regprocedure as sig, p.proname
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname in ('_require', '_log', '_branch', '_check_owned', '_customer', '_method_by_channel',
              '_sales_department', '_treasury_insert', '_stage_page',
              'my_company_id', 'is_company_admin', 'can_do', 'create_company', 'join_company', 'set_member',
              'add_staff', 'add_treasury_entry', 'update_treasury_department', 'delete_treasury_entry',
              'add_supplier', 'add_supplier_txn', 'cash_due_cheques', 'add_inspection', 'close_inspection',
              'update_inspection', 'delete_inspection', 'add_job', 'confirm_advance', 'finish_manufacturing',
              'finish_installation', 'confirm_final', 'update_job', 'set_job_note', 'delete_job')
    loop
        execute format('revoke all on function %s from public, anon', f.sig);
        if left(f.proname, 1) = '_' then
            execute format('revoke all on function %s from authenticated', f.sig);
        else
            execute format('grant execute on function %s to authenticated', f.sig);
        end if;
    end loop;
end $$;
