-- =====================================================================
--  02_security.sql — الأمان: كل شركة تشوف بياناتها بس
--
--  القاعدة:
--   - البرنامج يقدر "يقرا" الجداول مباشرة، بس بيانات شركته بس (RLS).
--   - أى "كتابة" لازم تعدّى من دوال 03_functions.sql، اللى بتفحص الصلاحيات
--     وبتنفذ العملية كلها مرة واحدة (يا تتعمل كلها يا متتعملش خالص).
--   - الاستثناء: مدير الشركة يقدر يعدّل جداول الإعدادات مباشرة.
-- =====================================================================

-- ========================= دوال مساعدة =========================

-- شركة المستخدم الحالى (لو حسابه مفعّل)
create or replace function public.my_company_id()
returns uuid language sql stable security definer set search_path = public as $$
    select company_id from public.profiles where user_id = auth.uid() and is_active
$$;

create or replace function public.is_company_admin()
returns boolean language sql stable security definer set search_path = public as $$
    select coalesce((select is_active and is_admin from public.profiles where user_id = auth.uid()), false)
$$;

-- p_action: 'view' | 'edit' | 'delete'
create or replace function public.can_do(p_page text, p_action text)
returns boolean language sql stable security definer set search_path = public as $$
    select coalesce((
        select p.is_active and (p.is_admin or case p_action
            when 'view'   then p_page = any(p.pages) or p_page = any(p.edit_pages)
            when 'edit'   then p_page = any(p.edit_pages)
            when 'delete' then p_page = any(p.delete_pages)
            else false end)
        from public.profiles p where p.user_id = auth.uid()
    ), false)
$$;

-- ========================= RLS =========================

do $$
declare
    t text;
    tenant_tables text[] := array['companies', 'branches', 'profiles', 'payment_methods', 'product_types',
        'departments', 'staff', 'customers', 'suppliers', 'jobs', 'inspections',
        'treasury_entries', 'supplier_txns', 'activity_log'];
    settings_tables text[] := array['branches', 'payment_methods', 'product_types', 'departments'];
begin
    foreach t in array tenant_tables loop
        execute format('alter table public.%I enable row level security', t);
        execute format('drop policy if exists tenant_read on public.%I', t);
    end loop;

    -- القراءة: نفس الشركة بس
    foreach t in array tenant_tables loop
        if t = 'companies' then
            execute 'create policy tenant_read on public.companies for select to authenticated
                     using (id = public.my_company_id())';
        elsif t = 'profiles' then
            -- المستخدم يشوف بروفايله حتى لو لسه متفعّلش، والمدير يشوف كل موظفين شركته
            execute 'create policy tenant_read on public.profiles for select to authenticated
                     using (user_id = auth.uid() or company_id = public.my_company_id())';
        else
            execute format('create policy tenant_read on public.%I for select to authenticated
                            using (company_id = public.my_company_id())', t);
        end if;
    end loop;

    -- الإعدادات: المدير بس يضيف/يعدّل (من غير مسح - بيوقفها بـ is_active)
    foreach t in array settings_tables loop
        execute format('drop policy if exists admin_insert on public.%I', t);
        execute format('drop policy if exists admin_update on public.%I', t);
        execute format('create policy admin_insert on public.%I for insert to authenticated
                        with check (public.is_company_admin() and company_id = public.my_company_id())', t);
        execute format('create policy admin_update on public.%I for update to authenticated
                        using (public.is_company_admin() and company_id = public.my_company_id())
                        with check (company_id = public.my_company_id())', t);
    end loop;
end $$;

-- ========================= الفواتير (Storage) =========================
-- الفواتير بتترفع فى bucket اسمه invoices، كل شركة فى فولدر باسم رقمها:
--   invoices/<company_id>/<اسم الملف>
-- (بدل حكاية الـ doPost فى وينتاج - هنا الرفع مباشر وآمن)

insert into storage.buckets (id, name, public)
values ('invoices', 'invoices', false)
on conflict (id) do nothing;

drop policy if exists invoices_read on storage.objects;
drop policy if exists invoices_upload on storage.objects;

create policy invoices_read on storage.objects for select to authenticated
    using (bucket_id = 'invoices'
           and (storage.foldername(name))[1] = public.my_company_id()::text);

create policy invoices_upload on storage.objects for insert to authenticated
    with check (bucket_id = 'invoices'
                and (storage.foldername(name))[1] = public.my_company_id()::text
                and (public.can_do('sales', 'edit')));
