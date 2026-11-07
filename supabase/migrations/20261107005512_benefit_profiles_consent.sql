-- Additive schema only. Apply to a confirmed development project after reviewing existing tables.
-- No HR records, names, emails, birth dates, API keys or source texts are seeded.
create table public.klink_benefit_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  profile jsonb not null default '{}'::jsonb,
  consent_version text not null check (consent_version = '2026-11-07'),
  created_at timestamptz not null default now(),
  constraint profile_is_object check (jsonb_typeof(profile) = 'object'),
  constraint no_unexpected_fields check (
    (profile - array['employment_consent','family_consent','hire_date','employment_type','children_ages','household_size']::text[]) = '{}'::jsonb
  ),
  constraint employment_consent_required check (
    coalesce(profile->>'employment_consent','false') = 'true'
    or (coalesce(profile->>'hire_date','') = '' and coalesce(profile->>'employment_type','') = '')
  ),
  constraint family_consent_required check (
    coalesce(profile->>'family_consent','false') = 'true'
    or (coalesce(profile->>'children_ages','') = '' and coalesce(profile->>'household_size','') = '')
  )
);

alter table public.klink_benefit_profiles enable row level security;
alter table public.klink_benefit_profiles force row level security;
revoke all on public.klink_benefit_profiles from public, anon, authenticated;
grant select, insert, update, delete on public.klink_benefit_profiles to authenticated;

create policy benefit_profile_select_own on public.klink_benefit_profiles
  for select to authenticated using (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  );
create policy benefit_profile_insert_own on public.klink_benefit_profiles
  for insert to authenticated with check (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  );
create policy benefit_profile_update_own on public.klink_benefit_profiles
  for update to authenticated using (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  ) with check (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  );
create policy benefit_profile_delete_own on public.klink_benefit_profiles
  for delete to authenticated using (
    (select auth.uid()) = user_id
    and coalesce((select auth.jwt())->>'is_anonymous','false') = 'false'
  );

comment on table public.klink_benefit_profiles is
  'Self-declared, consented recommendation inputs only; never authoritative HR facts or eligibility approval.';
