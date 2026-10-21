-- =====================================================================
--  04_reports.sql — جداول العرض والتقارير
--  الـ views دى security_invoker، يعنى بتتبع نفس قواعد RLS:
--  كل شركة بتشوف أرقامها بس.
-- =====================================================================

create or replace view public.treasury_view with (security_invoker = on) as
select t.id, t.company_id, t.branch_id, b.name as branch_name, t.entry_date,
       t.amount_in, t.amount_out, t.description, t.counterparty, t.source,
       t.payment_method_id, pm.name as payment_method, pm.channel,
       t.department_id, d.name as department, coalesce(d.is_sales, false) as is_sales,
       coalesce(d.in_profit, false) as in_profit,
       t.supplier_id, t.job_id, t.created_at
from public.treasury_entries t
join public.branches b on b.id = t.branch_id
left join public.payment_methods pm on pm.id = t.payment_method_id
left join public.departments d on d.id = t.department_id;

create or replace view public.jobs_view with (security_invoker = on) as
select j.id, j.company_id, j.branch_id, b.name as branch_name, b.is_main as is_main_branch,
       j.kind, j.status,
       case j.status when 'awaiting_advance' then 'تأكيد مقدم' when 'manufacturing' then 'تصنيع'
                     when 'installing' then 'تركيب' when 'awaiting_accounts' then 'تأكيد الحسابات'
                     else 'مكتمل' end as status_label,
       j.customer_id, c.name as customer_name, c.mobile as customer_mobile,
       j.place, j.product_type_id, pt.name as product_type, j.meters, j.price, j.advance,
       j.advance_method_id, am.name as advance_method,
       j.seller_id, s.name as seller_name, j.invoice_paths, j.description, j.note,
       j.craftsman, j.final_collected, j.final_method_id, fm.name as final_method,
       j.price - j.advance - case when j.status = 'completed' then coalesce(j.final_collected, 0) else 0 end
           as remaining,
       j.created_at, j.manufacturing_started_at, j.installing_started_at,
       j.install_finished_at, j.completed_at
from public.jobs j
join public.branches b on b.id = j.branch_id
join public.customers c on c.id = j.customer_id
left join public.product_types pt on pt.id = j.product_type_id
left join public.payment_methods am on am.id = j.advance_method_id
left join public.payment_methods fm on fm.id = j.final_method_id
left join public.staff s on s.id = j.seller_id;

create or replace view public.inspections_view with (security_invoker = on) as
select i.id, i.company_id, i.branch_id, b.name as branch_name, i.status,
       i.customer_id, c.name as customer_name, c.mobile as customer_mobile,
       i.place, i.product_type_id, pt.name as product_type, i.notes, i.created_at, i.closed_at
from public.inspections i
join public.branches b on b.id = i.branch_id
join public.customers c on c.id = i.customer_id
left join public.product_types pt on pt.id = i.product_type_id;

-- حساب كل مورد (بدل المعادلات اللى كانت فى شيت وينتاج)
create or replace view public.supplier_balances with (security_invoker = on) as
select s.id, s.company_id, s.name, s.material, s.mobile, s.supplier_type, s.created_at,
       coalesce(sum(t.amount) filter (where t.txn_type = 'invoice'), 0)                              as invoices,
       coalesce(sum(t.amount) filter (where t.txn_type = 'return'), 0)                               as returns,
       coalesce(sum(t.amount) filter (where t.txn_type = 'cash_payment'), 0)                         as cash_paid,
       coalesce(sum(t.amount) filter (where t.txn_type = 'bank_payment'), 0)                         as bank_paid,
       coalesce(sum(t.amount) filter (where t.txn_type = 'cheque' and t.cheque_status = 'due'), 0)    as cheques_due,
       coalesce(sum(t.amount) filter (where t.txn_type = 'cheque' and t.cheque_status = 'cashed'), 0) as cheques_cashed,
       coalesce(sum(case when t.txn_type = 'invoice' then t.amount
                         when t.txn_type in ('return', 'cash_payment', 'bank_payment', 'cheque') then -t.amount
                         else 0 end), 0) as remaining
from public.suppliers s
left join public.supplier_txns t on t.supplier_id = s.id
group by s.id;

create or replace view public.due_cheques_view with (security_invoker = on) as
select t.id, t.company_id, t.supplier_id, s.name as supplier_name, t.cheque_no, t.amount, t.due_date,
       (t.due_date - current_date) as days_left
from public.supplier_txns t
join public.suppliers s on s.id = t.supplier_id
where t.txn_type = 'cheque' and t.cheque_status = 'due';

-- ========================= كروت الداش بورد =========================
-- p_branch_id = null ← كل الفروع
create or replace function public.dashboard_kpis(p_branch_id uuid default null)
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
    v_company uuid := public.my_company_id();
    v_start date;
    r jsonb;
begin
    if v_company is null then raise exception 'حسابك مش متفعّل فى أى شركة'; end if;
    select profit_start_date into v_start from public.companies where id = v_company;
    select jsonb_build_object(
        'wared',     coalesce(sum(amount_in), 0),
        'monsaref',  coalesce(sum(amount_out), 0),
        'raseed',    coalesce(sum(amount_in) - sum(amount_out), 0),
        'amaliyat',  count(*),
        'profit_sales',    coalesce(sum(amount_in)  filter (where is_sales  and (v_start is null or entry_date >= v_start)), 0),
        'profit_expenses', coalesce(sum(amount_out) filter (where in_profit and (v_start is null or entry_date >= v_start)), 0)
    ) into r
    from public.treasury_view
    where company_id = v_company and (p_branch_id is null or branch_id = p_branch_id);

    r := r || jsonb_build_object('rebh', (r->>'profit_sales')::numeric - (r->>'profit_expenses')::numeric);

    r := r || (select jsonb_build_object(
        'open_jobs',        count(*),
        'open_value',       coalesce(sum(price), 0),
        'collected_advance', coalesce(sum(advance), 0),
        'customers_remaining', coalesce(sum(remaining), 0))
        from public.jobs_view
        where company_id = v_company and status <> 'completed'
              and (p_branch_id is null or branch_id = p_branch_id));

    r := r || (select jsonb_build_object(
        'suppliers_due', coalesce(sum(remaining), 0),
        'cheques_due',   coalesce(sum(cheques_due), 0))
        from public.supplier_balances where company_id = v_company);
    return r;
end $$;

-- ربح كل شهر (من تاريخ بداية الربح)
create or replace function public.profit_by_month(p_branch_id uuid default null)
returns table (month date, sales numeric, expenses numeric, profit numeric)
language sql stable security invoker set search_path = public as $$
    select date_trunc('month', entry_date)::date as month,
           coalesce(sum(amount_in) filter (where is_sales), 0)   as sales,
           coalesce(sum(amount_out) filter (where in_profit), 0) as expenses,
           coalesce(sum(amount_in) filter (where is_sales), 0) - coalesce(sum(amount_out) filter (where in_profit), 0)
    from public.treasury_view
    where company_id = public.my_company_id()
      and (p_branch_id is null or branch_id = p_branch_id)
      and entry_date >= coalesce((select profit_start_date from public.companies where id = public.my_company_id()),
                                 '1900-01-01'::date)
    group by 1 order by 1
$$;

-- قيمة التعاقدات اللى اتمضت كل شهر (العقود بس، مش الصيانة)
create or replace function public.contracts_value_by_month(p_branch_id uuid default null)
returns table (month date, contracts bigint, total_value numeric)
language sql stable security invoker set search_path = public as $$
    select date_trunc('month', created_at)::date, count(*), coalesce(sum(price), 0)
    from public.jobs_view
    where company_id = public.my_company_id() and kind = 'contract'
      and (p_branch_id is null or branch_id = p_branch_id)
    group by 1 order by 1
$$;

grant execute on function public.dashboard_kpis(uuid), public.profit_by_month(uuid),
    public.contracts_value_by_month(uuid) to authenticated;
revoke execute on function public.dashboard_kpis(uuid), public.profit_by_month(uuid),
    public.contracts_value_by_month(uuid) from public, anon;
