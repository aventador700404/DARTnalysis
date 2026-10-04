-- 공공데이터포털 서울 중계(functions/datagokr-relay) 인증용 비밀값.
-- DB 안에서 무작위로 만들어 Vault에 넣는다 → 사람이 비밀번호를 만들거나 옮겨 적을 필요 없음.
--   · 중계(Edge Function)는 service role로 아래 함수를 불러 꺼내 쓰고
--   · 파이프라인(GitHub Actions)은 이미 가진 SUPABASE_DB_URL로 같은 함수를 불러 꺼내 쓴다.
do $$
begin
  if not exists (select 1 from vault.secrets where name = 'datagokr_relay_secret') then
    perform vault.create_secret(encode(extensions.gen_random_bytes(32), 'hex'), 'datagokr_relay_secret',
                                '공공데이터포털 서울 중계 인증 (자동 생성)');
  end if;
end $$;

create or replace function public.datagokr_relay_secret()
returns text language sql stable security definer set search_path = '' as $$
  select decrypted_secret from vault.decrypted_secrets where name = 'datagokr_relay_secret' limit 1;
$$;
-- 웹(anon)·로그인 사용자는 못 부르고, 서버(service role)만
revoke all on function public.datagokr_relay_secret() from public, anon, authenticated;
grant execute on function public.datagokr_relay_secret() to service_role;
