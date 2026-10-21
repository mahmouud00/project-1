-- =====================================================================
--  06_settings.sql — إضافات صفحة الإعدادات
--  شغّله مرة واحدة بعد 01 → 04 (زيهم بالظبط: انسخ ← الصق ← Run).
--  فى آخره اختبار صغير بيطلّع PASS/FAIL وبيمسح اللى عمله.
-- =====================================================================

-- 1) إيميل الموظف: عشان المدير يعرف مين اللى طالب ينضم
alter table public.profiles add column if not exists email text;

create or replace function public._profile_email()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    if new.email is null then
        select email into new.email from auth.users where id = new.user_id;
    end if;
    return new;
end $$;

drop trigger if exists profiles_email on public.profiles;
create trigger profiles_email before insert on public.profiles
    for each row execute function public._profile_email();

update public.profiles p set email = u.email
from auth.users u where u.id = p.user_id and p.email is null;

-- 2) المدير بيعدّل بيانات الشركة
create or replace function public.update_company(p_name text, p_profit_start_date date, p_require_invoice boolean)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public.my_company_id();
begin
    if not public.is_company_admin() then raise exception 'المدير بس يقدر يعدّل بيانات الشركة'; end if;
    if length(btrim(coalesce(p_name, ''))) = 0 then raise exception 'اسم الشركة مطلوب'; end if;
    update public.companies
    set name = btrim(p_name), profit_start_date = p_profit_start_date,
        require_invoice = coalesce(p_require_invoice, true)
    where id = v_company;
    perform public._log(v_company, 'تعديل بيانات الشركة', p_name);
end $$;

-- 3) كود انضمام جديد (لو القديم اتسرّب)
create or replace function public.regenerate_join_code()
returns text language plpgsql security definer set search_path = public as $$
declare v_company uuid := public.my_company_id(); v_code text;
begin
    if not public.is_company_admin() then raise exception 'المدير بس يقدر يغيّر الكود'; end if;
    v_code := upper(substr(md5(gen_random_uuid()::text), 1, 8));
    update public.companies set join_code = v_code where id = v_company;
    perform public._log(v_company, 'تغيير كود الانضمام', null);
    return v_code;
end $$;

revoke all on function public._profile_email() from public, anon, authenticated;
revoke all on function public.update_company(text, date, boolean) from public, anon;
revoke all on function public.regenerate_join_code() from public, anon;
grant execute on function public.update_company(text, date, boolean) to authenticated;
grant execute on function public.regenerate_join_code() to authenticated;

-- ========================= اختبار =========================
drop table if exists pg_temp.test_results;
create temp table test_results (n serial, ok boolean, name text);
create or replace function pg_temp.ok(p_name text, p_ok boolean) returns void language sql as $$
    insert into pg_temp.test_results (ok, name) values (coalesce(p_ok, false), p_name)
$$;
create or replace function pg_temp.as_user(u uuid) returns void language plpgsql as $$
begin
    perform set_config('request.jwt.claims',
        case when u is null then '' else json_build_object('sub', u::text, 'role', 'authenticated')::text end, false);
    perform set_config('request.jwt.claim.sub', coalesce(u::text, ''), false);
end $$;

do $test$
declare
    ua uuid := gen_random_uuid(); uc uuid := gen_random_uuid(); ud uuid := gen_random_uuid();
    ca uuid; v_old text; v_new text; e_msg text;
begin
    insert into auth.users (instance_id, id, aud, role, email) values
        ('00000000-0000-0000-0000-000000000000', ua, 'authenticated', 'authenticated', 'admin-' || ua || '@example.com'),
        ('00000000-0000-0000-0000-000000000000', uc, 'authenticated', 'authenticated', 'worker-' || uc || '@example.com'),
        ('00000000-0000-0000-0000-000000000000', ud, 'authenticated', 'authenticated', 'late-' || ud || '@example.com');
    begin
        perform pg_temp.as_user(ua);
        ca := public.create_company('شركة اختبار الإعدادات', 'مدير');
        perform pg_temp.ok('admin email saved on profile',
            (select email from public.profiles where user_id = ua) = 'admin-' || ua || '@example.com');

        select join_code into v_old from public.companies where id = ca;
        perform pg_temp.as_user(uc);
        perform public.join_company(v_old, 'موظف');
        perform pg_temp.ok('joining employee email visible to admin',
            (select email from public.profiles where user_id = uc) = 'worker-' || uc || '@example.com');
        begin
            perform public.update_company('اسم تانى', null, false);
            perform pg_temp.ok('non-admin cannot edit company', false);
        exception when others then perform pg_temp.ok('non-admin cannot edit company', true); end;

        perform pg_temp.as_user(ua);
        perform public.update_company('الشركة الجديدة', date '2026-08-01', false);
        perform pg_temp.ok('admin updates company settings',
            (select name = 'الشركة الجديدة' and profit_start_date = date '2026-08-01' and not require_invoice
             from public.companies where id = ca));
        v_new := public.regenerate_join_code();
        perform pg_temp.ok('join code regenerated', v_new is not null and v_new <> v_old);
        begin
            perform pg_temp.as_user(ud);
            perform public.join_company(v_old, 'حد تانى');
            perform pg_temp.ok('old join code no longer works', false);
        exception when others then
            perform pg_temp.ok('old join code no longer works', sqlerrm like '%كود%');
        end;
    exception when others then
        get stacked diagnostics e_msg = message_text;
        perform pg_temp.ok('💥 توقف: ' || e_msg, false);
    end;
    perform pg_temp.as_user(null);
    delete from public.companies where id = ca;
    delete from auth.users where id in (ua, uc, ud);
end $test$;

select n as "#", case when ok then '✅ PASS' else '❌ FAIL' end as result, name as test
from pg_temp.test_results
union all
select 0, (select count(*) filter (where ok) from pg_temp.test_results) || ' / '
          || (select count(*) from pg_temp.test_results), '📊 المجموع'
order by 1;
