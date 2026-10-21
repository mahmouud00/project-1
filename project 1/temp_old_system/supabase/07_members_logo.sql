-- =====================================================================
--  07_members_logo.sql — حذف موظف + لوجو الشركة
--  شغّله مرة واحدة (انسخ ← الصق ← Run). فى آخره اختبار بيطلّع PASS/FAIL.
-- =====================================================================

-- 1) المدير يشيل موظف من الشركة خالص (الحساب بيفضل موجود، ويقدر ينضم تانى بالكود)
--    ملحوظة: "إيقاف" الموظف من غير ما يتشال = set_member بـ is_active = false
create or replace function public.remove_member(p_user_id uuid)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public.my_company_id(); v_name text;
begin
    if not public.is_company_admin() then raise exception 'المدير بس يقدر يشيل موظفين'; end if;
    if p_user_id = auth.uid() then raise exception 'مينفعش تشيل نفسك من الشركة'; end if;
    delete from public.profiles where user_id = p_user_id and company_id = v_company
    returning full_name into v_name;
    if v_name is null then raise exception 'الموظف ده مش تبع شركتك'; end if;
    perform public._log(v_company, 'حذف موظف من الشركة', v_name);
end $$;

-- 2) لوجو الشركة: الملف بيترفع فى company-logos/<company_id>/... والدالة دى بتسجل مكانه
create or replace function public.set_company_logo(p_logo_path text)
returns void language plpgsql security definer set search_path = public as $$
declare v_company uuid := public.my_company_id();
begin
    if not public.is_company_admin() then raise exception 'المدير بس يقدر يغيّر اللوجو'; end if;
    if p_logo_path is not null and split_part(p_logo_path, '/', 1) <> v_company::text then
        raise exception 'مكان اللوجو غير صحيح';
    end if;
    update public.companies set logo_path = p_logo_path where id = v_company;
    perform public._log(v_company, 'تغيير لوجو الشركة', null);
end $$;

revoke all on function public.remove_member(uuid) from public, anon;
revoke all on function public.set_company_logo(text) from public, anon;
grant execute on function public.remove_member(uuid) to authenticated;
grant execute on function public.set_company_logo(text) to authenticated;

-- 3) مكان اللوجوهات: خاص (مش علنى)، 2 ميجا بالكتير، صور PNG/JPG بس
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('company-logos', 'company-logos', false, 2097152, array['image/png', 'image/jpeg'])
on conflict (id) do nothing;

drop policy if exists logos_read on storage.objects;
drop policy if exists logos_upload on storage.objects;
create policy logos_read on storage.objects for select to authenticated
    using (bucket_id = 'company-logos'
           and (storage.foldername(name))[1] = public.my_company_id()::text);
create policy logos_upload on storage.objects for insert to authenticated
    with check (bucket_id = 'company-logos'
                and (storage.foldername(name))[1] = public.my_company_id()::text
                and public.is_company_admin());

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
    ua uuid := gen_random_uuid(); uw uuid := gen_random_uuid();
    ca uuid; v_code text; e_msg text;
begin
    insert into auth.users (instance_id, id, aud, role, email) values
        ('00000000-0000-0000-0000-000000000000', ua, 'authenticated', 'authenticated', 'boss-' || ua || '@example.com'),
        ('00000000-0000-0000-0000-000000000000', uw, 'authenticated', 'authenticated', 'staff-' || uw || '@example.com');
    begin
        perform pg_temp.as_user(ua);
        ca := public.create_company('شركة اختبار الموظفين', 'مدير');
        select join_code into v_code from public.companies where id = ca;
        perform pg_temp.as_user(uw);
        perform public.join_company(v_code, 'موظف');
        perform pg_temp.as_user(ua);
        perform public.set_member(uw, true, false, '{sales}', '{sales}', '{}', 'سيلز');

        perform public.set_member(uw, false, false, '{sales}', '{sales}', '{}', 'سيلز');
        perform pg_temp.ok('admin can suspend an employee (keeps his pages)',
            (select not is_active and pages = '{sales}' from public.profiles where user_id = uw));

        perform pg_temp.as_user(uw);
        begin
            perform public.remove_member(ua);
            perform pg_temp.ok('employee cannot remove anyone', false);
        exception when others then perform pg_temp.ok('employee cannot remove anyone', true); end;

        perform pg_temp.as_user(ua);
        begin
            perform public.remove_member(ua);
            perform pg_temp.ok('admin cannot remove himself', false);
        exception when others then perform pg_temp.ok('admin cannot remove himself', true); end;

        perform public.remove_member(uw);
        perform pg_temp.ok('admin removes employee from the company',
            not exists (select 1 from public.profiles where user_id = uw));

        perform pg_temp.as_user(uw);
        perform public.join_company(v_code, 'موظف راجع');
        perform pg_temp.ok('removed employee can rejoin with the code (pending again)',
            (select not is_active from public.profiles where user_id = uw));

        perform pg_temp.as_user(ua);
        begin
            perform public.set_company_logo(gen_random_uuid()::text || '/logo.png');
            perform pg_temp.ok('logo outside company folder rejected', false);
        exception when others then perform pg_temp.ok('logo outside company folder rejected', true); end;
        perform public.set_company_logo(ca::text || '/logo-1.png');
        perform pg_temp.ok('logo path saved',
            (select logo_path from public.companies where id = ca) = ca::text || '/logo-1.png');
        perform pg_temp.ok('logos bucket exists (private, images only)',
            exists (select 1 from storage.buckets where id = 'company-logos' and not public));
    exception when others then
        get stacked diagnostics e_msg = message_text;
        perform pg_temp.ok('💥 توقف: ' || e_msg, false);
    end;
    perform pg_temp.as_user(null);
    delete from public.companies where id = ca;
    delete from auth.users where id in (ua, uw);
end $test$;

select n as "#", case when ok then '✅ PASS' else '❌ FAIL' end as result, name as test
from pg_temp.test_results
union all
select 0, (select count(*) filter (where ok) from pg_temp.test_results) || ' / '
          || (select count(*) from pg_temp.test_results), '📊 المجموع'
order by 1;
