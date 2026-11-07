-- Prepared offline; not applied to the inaccessible hosted project.
-- Provision active employees only through an authorized organization administrator.
-- No employee, account, password or source-document rows are seeded here.

create table public.klink_employee_memberships (
  user_id uuid primary key references auth.users(id) on delete cascade,
  company text not null check (company = 'KTCS'),
  active boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.klink_employee_memberships enable row level security;
alter table public.klink_employee_memberships force row level security;
revoke all on public.klink_employee_memberships from public, anon, authenticated;
grant select on public.klink_employee_memberships to authenticated;

create policy employee_membership_select_own on public.klink_employee_memberships
  for select to authenticated using (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  );

-- No INSERT/UPDATE/DELETE grant or policy is available to ordinary users.
-- A JWT or user-editable user_metadata value cannot self-provision membership.

alter policy benefit_profile_select_own on public.klink_benefit_profiles using (
  (select auth.uid()) = user_id
  and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  and exists (
    select 1 from public.klink_employee_memberships m
    where m.user_id = (select auth.uid()) and m.company = 'KTCS' and m.active
  )
);

alter policy benefit_profile_insert_own on public.klink_benefit_profiles with check (
  (select auth.uid()) = user_id
  and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  and exists (
    select 1 from public.klink_employee_memberships m
    where m.user_id = (select auth.uid()) and m.company = 'KTCS' and m.active
  )
);

alter policy benefit_profile_update_own on public.klink_benefit_profiles using (
  (select auth.uid()) = user_id
  and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  and exists (
    select 1 from public.klink_employee_memberships m
    where m.user_id = (select auth.uid()) and m.company = 'KTCS' and m.active
  )
) with check (
  (select auth.uid()) = user_id
  and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  and exists (
    select 1 from public.klink_employee_memberships m
    where m.user_id = (select auth.uid()) and m.company = 'KTCS' and m.active
  )
);

alter policy benefit_profile_delete_own on public.klink_benefit_profiles using (
  (select auth.uid()) = user_id
  and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  and exists (
    select 1 from public.klink_employee_memberships m
    where m.user_id = (select auth.uid()) and m.company = 'KTCS' and m.active
  )
);

comment on table public.klink_employee_memberships is
  'Organization-provisioned membership only; an authenticated account alone is not an authorized employee.';
