-- =====================================================================
--  05_tests.sql — اختبار شامل لقاعدة البيانات
--  شغّله بعد الملفات 01 → 04. بيعمل شركتين تجريبيين و3 مستخدمين،
--  بيعدّى الدورة كلها، بيطلّع جدول PASS/FAIL، وفى الآخر بيمسح كل حاجة عملها.
-- =====================================================================

drop table if exists pg_temp.test_results;
create temp table test_results (n serial, ok boolean, name text);

create or replace function pg_temp.ok(p_name text, p_ok boolean) returns void language sql as $$
    insert into pg_temp.test_results (ok, name) values (coalesce(p_ok, false), p_name)
$$;

-- يخلّى auth.uid() يرجّع المستخدم ده (زى ما يكون هو اللى عامل login)
create or replace function pg_temp.as_user(u uuid) returns void language plpgsql as $$
begin
    perform set_config('request.jwt.claims',
        case when u is null then '' else json_build_object('sub', u::text, 'role', 'authenticated')::text end, false);
    perform set_config('request.jwt.claim.sub', coalesce(u::text, ''), false);
end $$;

do $test$
declare
    ua uuid := gen_random_uuid();   -- مدير شركة أ
    ub uuid := gen_random_uuid();   -- مدير شركة ب
    uc uuid := gen_random_uuid();   -- موظف مصنع فى شركة أ
    ca uuid; cb uuid;
    m_cash uuid; m_bank uuid; m_wallet uuid; b_method uuid;
    d_sales uuid; d_buy uuid; p_shutter uuid; v_seller uuid; v_sup uuid;
    v_job bigint; v_maint bigint; v_t bigint; v_pay_entry bigint; v_final_entry bigint;
    v_n int; v_cnt int; v_cnt2 int; v_txt text; v_kpi jsonb; v_num numeric;
    e_msg text; e_ctx text;
begin
    insert into auth.users (instance_id, id, aud, role, email) values
        ('00000000-0000-0000-0000-000000000000', ua, 'authenticated', 'authenticated', 'test-a-' || ua || '@example.com'),
        ('00000000-0000-0000-0000-000000000000', ub, 'authenticated', 'authenticated', 'test-b-' || ub || '@example.com'),
        ('00000000-0000-0000-0000-000000000000', uc, 'authenticated', 'authenticated', 'test-c-' || uc || '@example.com');

    begin  -- ======== كل الاختبارات جوا البلوك ده ========

    -- ---------- الشركات والموظفين ----------
    perform pg_temp.as_user(ua);
    ca := public.create_company('شركة اختبار أ', 'مدير أ');
    perform pg_temp.ok('create company A', ca is not null);
    perform pg_temp.ok('default settings created (5 payment methods, 6 departments)',
        (select count(*) from public.payment_methods where company_id = ca) = 5
        and (select count(*) from public.departments where company_id = ca) = 6);
    begin
        perform public.create_company('تانى', 'x');
        perform pg_temp.ok('second company for same user blocked', false);
    exception when others then perform pg_temp.ok('second company for same user blocked', true); end;

    perform pg_temp.as_user(ub);
    cb := public.create_company('شركة اختبار ب', 'مدير ب');
    select id into b_method from public.payment_methods where company_id = cb and channel = 'cash';

    perform pg_temp.as_user(uc);
    select join_code into v_txt from public.companies where id = ca;
    perform public.join_company(lower(v_txt), 'عامل المصنع');
    perform pg_temp.ok('employee joins with company code (inactive until approved)',
        (select not is_active from public.profiles where user_id = uc));
    begin
        perform public.add_treasury_entry('in', 10, 'محاولة');
        perform pg_temp.ok('inactive employee cannot write', false);
    exception when others then perform pg_temp.ok('inactive employee cannot write', true); end;

    perform pg_temp.as_user(ua);
    perform public.set_member(uc, true, false, '{factory}', '{factory}', '{}', 'مصنع');
    perform pg_temp.ok('admin activates employee with factory-only rights',
        (select is_active and edit_pages = '{factory}' from public.profiles where user_id = uc));

    select id into m_cash from public.payment_methods where company_id = ca and channel = 'cash';
    select id into m_bank from public.payment_methods where company_id = ca and channel = 'bank';
    select id into m_wallet from public.payment_methods where company_id = ca and name = 'فودافون كاش';
    select id into d_sales from public.departments where company_id = ca and is_sales;
    select id into d_buy from public.departments where company_id = ca and name = 'المشتريات';
    select id into p_shutter from public.product_types where company_id = ca and name = 'شاتر';

    -- ---------- الخزينة ----------
    v_t := public.add_treasury_entry('in', 1000, 'رصيد افتتاحى', m_cash);
    perform public.add_treasury_entry('out', 300, 'خامات', m_cash, d_buy, current_date - 3);
    perform pg_temp.ok('treasury entries saved',
        (select count(*) from public.treasury_entries where company_id = ca) = 2);
    begin
        perform public.add_treasury_entry('in', 0, 'صفر');
        perform pg_temp.ok('zero amount rejected', false);
    exception when others then perform pg_temp.ok('zero amount rejected', true); end;
    begin
        perform public.add_treasury_entry('in', 50, 'بطريقة دفع شركة تانية', b_method);
        perform pg_temp.ok('payment method of another company rejected', false);
    exception when others then perform pg_temp.ok('payment method of another company rejected', true); end;

    -- ---------- الموردين والشيكات ----------
    v_sup := public.add_supplier('مورد اختبار', 'قطاعات', '01033100340', 'وكيل');
    perform pg_temp.ok('supplier mobile keeps leading zero',
        (select mobile from public.suppliers where id = v_sup) = '01033100340');
    begin
        perform public.add_supplier('مورد اختبار');
        perform pg_temp.ok('duplicate supplier rejected', false);
    exception when others then perform pg_temp.ok('duplicate supplier rejected', true); end;

    perform public.add_supplier_txn(v_sup, 'invoice', 5000, 'فاتورة 1');
    perform public.add_supplier_txn(v_sup, 'cash_payment', 2000, 'دفعة أولى');
    select treasury_entry_id into v_pay_entry from public.supplier_txns
        where supplier_id = v_sup and txn_type = 'cash_payment';
    perform pg_temp.ok('cash payment posted to treasury as outflow',
        (select amount_out = 2000 and supplier_id = v_sup and source = 'supplier_payment'
         from public.treasury_entries where id = v_pay_entry));
    perform public.add_supplier_txn(v_sup, 'cheque', 1000, null, '777', current_date - 1);
    perform public.add_supplier_txn(v_sup, 'cheque', 500, null, '778', current_date + 10);
    begin
        perform public.add_supplier_txn(v_sup, 'cheque', 10, null, '1', null);
        perform pg_temp.ok('cheque without due date rejected', false);
    exception when others then perform pg_temp.ok('cheque without due date rejected', true); end;
    perform pg_temp.ok('supplier balance: 5000 - 2000 - 1500 cheques = 1500',
        (select remaining = 1500 and cheques_due = 1500 from public.supplier_balances where id = v_sup));

    v_n := public.cash_due_cheques();
    perform pg_temp.ok('only the due cheque was cashed', v_n = 1);
    perform pg_temp.ok('cashed cheque in treasury with its due date',
        exists (select 1 from public.treasury_entries where company_id = ca and source = 'cheque'
                and amount_out = 1000 and entry_date = current_date - 1 and description like 'صرف شيك رقم 777%'));
    perform pg_temp.ok('running cash_due_cheques again does nothing', public.cash_due_cheques() = 0);

    v_n := public.delete_treasury_entry(v_pay_entry);
    perform pg_temp.ok('deleting payment entry also deletes its supplier txn', v_n = 1
        and not exists (select 1 from public.supplier_txns where supplier_id = v_sup and txn_type = 'cash_payment'));
    perform pg_temp.ok('supplier balance after delete = 3500',
        (select remaining from public.supplier_balances where id = v_sup) = 3500);

    -- ---------- دورة تعاقد كاملة ----------
    v_seller := public.add_staff('سيلز اختبار', '0100');
    begin
        perform public.add_job('contract', 'كريم', '01011112222', 'التجمع', p_shutter, 30000, 8, 5000, m_wallet, v_seller, '{}');
        perform pg_temp.ok('contract without invoice rejected', false);
    exception when others then perform pg_temp.ok('contract without invoice rejected', true); end;
    begin
        perform public.add_job('contract', 'كريم', '01011112222', 'التجمع', p_shutter, 30000, 0, 5000, m_wallet,
                               v_seller, array[ca::text || '/inv.pdf']);
        perform pg_temp.ok('contract without meters rejected', false);
    exception when others then perform pg_temp.ok('contract without meters rejected', true); end;

    v_job := public.add_job('contract', 'كريم', '01011112222', 'التجمع', p_shutter, 30000, 8, 5000, m_wallet,
                            v_seller, array[ca::text || '/inv.pdf']);
    perform pg_temp.ok('contract created awaiting advance',
        (select status = 'awaiting_advance' and remaining = 25000 from public.jobs_view where id = v_job));

    perform pg_temp.as_user(uc);
    begin
        perform public.confirm_advance(v_job);
        perform pg_temp.ok('factory employee cannot confirm advance', false);
    exception when others then perform pg_temp.ok('factory employee cannot confirm advance', true); end;

    perform pg_temp.as_user(ua);
    v_t := public.confirm_advance(v_job);
    perform pg_temp.ok('advance posted to treasury under sales department',
        (select amount_in = 5000 and department_id = d_sales and payment_method_id = m_wallet and job_id = v_job
         from public.treasury_entries where id = v_t));
    perform pg_temp.ok('job moved to manufacturing',
        (select status = 'manufacturing' and manufacturing_started_at is not null from public.jobs where id = v_job));
    begin
        perform public.confirm_advance(v_job);
        perform pg_temp.ok('double confirm blocked (no duplicate money)', false);
    exception when others then perform pg_temp.ok('double confirm blocked (no duplicate money)', true); end;
    begin
        perform public.update_job(v_job, null, null, 9000);
        perform pg_temp.ok('advance cannot change after it was posted', false);
    exception when others then perform pg_temp.ok('advance cannot change after it was posted', true); end;
    begin
        perform public.delete_job(v_job);
        perform pg_temp.ok('job with posted money cannot be deleted', false);
    exception when others then perform pg_temp.ok('job with posted money cannot be deleted', true); end;
    begin
        perform public.delete_treasury_entry(v_t);
        perform pg_temp.ok('advance entry cannot be deleted from treasury', false);
    exception when others then perform pg_temp.ok('advance entry cannot be deleted from treasury', true); end;

    perform pg_temp.as_user(uc);
    perform public.set_job_note(v_job, 'مستنى زجاج');
    perform public.finish_manufacturing(v_job);
    perform pg_temp.ok('factory employee adds note and finishes manufacturing',
        (select status = 'installing' and note = 'مستنى زجاج' from public.jobs where id = v_job));
    begin
        perform public.finish_installation(v_job, 25000, m_cash, 'عم سيد');
        perform pg_temp.ok('factory employee cannot close installation', false);
    exception when others then perform pg_temp.ok('factory employee cannot close installation', true); end;

    perform pg_temp.as_user(ua);
    begin
        perform public.finish_installation(v_job, 25000, m_cash, '');
        perform pg_temp.ok('installation needs craftsman name', false);
    exception when others then perform pg_temp.ok('installation needs craftsman name', true); end;
    perform public.finish_installation(v_job, 25000, m_cash, 'عم سيد');
    v_final_entry := public.confirm_final(v_job);
    perform pg_temp.ok('final collection posted to treasury',
        (select amount_in = 25000 and source = 'job_final' from public.treasury_entries where id = v_final_entry));
    perform pg_temp.ok('job completed with zero remaining (stays in the table, nothing moved)',
        (select status = 'completed' and remaining = 0 and craftsman = 'عم سيد' from public.jobs_view where id = v_job));

    v_maint := public.add_job('maintenance', 'ليلى', '', '', p_shutter, 900, 0, 0, null, null, '{}', 'تسريب');
    perform pg_temp.ok('maintenance goes straight to installing (no invoice needed)',
        (select status = 'installing' and installing_started_at is not null from public.jobs where id = v_maint));

    -- ---------- المعاينات ----------
    v_t := public.add_inspection('سامى', '01122233344', 'المعادى', p_shutter, 'بعد العصر');
    perform public.add_inspection('سامى', '01122233344', 'المعادى 2');
    perform pg_temp.ok('same mobile reuses the same customer',
        (select count(*) from public.customers where company_id = ca and mobile = '01122233344') = 1);
    perform public.close_inspection(v_t);
    begin
        perform public.close_inspection(v_t);
        perform pg_temp.ok('closing a closed inspection rejected', false);
    exception when others then perform pg_temp.ok('closing a closed inspection rejected', true); end;
    perform public.delete_inspection(v_t);
    perform pg_temp.ok('inspection close + delete',
        not exists (select 1 from public.inspections where id = v_t));

    -- ---------- كروت الداش بورد ----------
    v_kpi := public.dashboard_kpis();
    perform pg_temp.ok('KPI in/out: 31000 in, 1300 out → balance 29700',
        (v_kpi->>'wared')::numeric = 31000 and (v_kpi->>'monsaref')::numeric = 1300
        and (v_kpi->>'raseed')::numeric = 29700);
    perform pg_temp.ok('KPI profit: sales 30000 - costs 300 = 29700',
        (v_kpi->>'rebh')::numeric = 29700);
    perform pg_temp.ok('KPI open jobs: only the 900 maintenance',
        (v_kpi->>'open_jobs')::int = 1 and (v_kpi->>'customers_remaining')::numeric = 900);
    perform pg_temp.ok('KPI suppliers: 3500 due, 500 in cheques',
        (v_kpi->>'suppliers_due')::numeric = 3500 and (v_kpi->>'cheques_due')::numeric = 500);
    perform pg_temp.ok('profit by month returns this month',
        exists (select 1 from public.profit_by_month() where month = date_trunc('month', current_date)::date
                and sales = 30000));

    -- ---------- عزل الشركات (RLS) ----------
    perform pg_temp.as_user(ub);
    execute 'set local role authenticated';
    select count(*) into v_cnt from public.treasury_entries;
    select count(*) into v_cnt2 from public.jobs_view;
    begin
        execute 'insert into public.treasury_entries (company_id, branch_id, amount_in, description) '
             || 'select company_id, id, 1, ''hack'' from public.branches limit 1';
        v_txt := 'inserted';
    exception when others then v_txt := 'blocked'; end;
    execute 'reset role';
    perform pg_temp.ok('company B sees none of company A data', v_cnt = 0 and v_cnt2 = 0);
    perform pg_temp.ok('direct table writes are blocked (must use the functions)', v_txt = 'blocked');

    perform pg_temp.as_user(ua);
    execute 'set local role authenticated';
    select count(*) into v_cnt from public.treasury_entries;
    select count(*) into v_cnt2 from public.companies;
    execute 'reset role';
    perform pg_temp.ok('company A sees its own data only', v_cnt > 0 and v_cnt2 = 1);

    perform pg_temp.as_user(ub);
    begin
        perform public.confirm_final(v_maint);
        perform pg_temp.ok('company B cannot touch company A jobs', false);
    exception when others then perform pg_temp.ok('company B cannot touch company A jobs', true); end;

    exception when others then
        get stacked diagnostics e_msg = message_text, e_ctx = pg_exception_context;
        execute 'reset role';
        perform pg_temp.ok('💥 توقف: ' || e_msg || ' | ' || e_ctx, false);
    end;

    -- ---------- تنضيف ----------
    perform pg_temp.as_user(null);
    delete from public.companies where id in (ca, cb);
    delete from auth.users where id in (ua, ub, uc);
end $test$;

select n as "#", case when ok then '✅ PASS' else '❌ FAIL' end as result, name as test
from pg_temp.test_results
union all
select 0, (select count(*) filter (where ok) from pg_temp.test_results) || ' / '
          || (select count(*) from pg_temp.test_results), '📊 المجموع'
order by 1;
