-- 1분마다 새 공시 확인 (Supabase Cron → Edge Function)  — 명세서 5.2
-- Edge Function(poll-disclosures)을 배포한 뒤 SQL Editor에서 한 번 실행.
--
-- ⚠️ 크론 시간은 UTC 기준. 한국 시간(KST) = UTC + 9
--    평일 KST 07:00~19:59 → UTC 전날 22:00~23:59 + 당일 00:00~10:59

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- ① 비밀값을 Vault에 저장 (값은 본인 프로젝트 것으로 바꾸기)
--    project_url : https://<project-ref>.supabase.co
--    cron_secret : 아무 긴 랜덤 문자열. Edge Function 쪽에도 같은 값을 CRON_SECRET으로 등록
--                  (supabase secrets set CRON_SECRET=...)
select vault.create_secret('https://YOUR-PROJECT-REF.supabase.co', 'project_url');
select vault.create_secret('YOUR-LONG-RANDOM-STRING', 'cron_secret');

-- ② 호출 함수
create or replace function public.invoke_poll_disclosures() returns void
language sql security definer as $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/poll-disclosures',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'cron_secret')
    ),
    body := '{}'::jsonb
  );
$$;

-- ③ 일정 등록
-- KST 월~금 07:00~08:59  = UTC 일~목 22:00~23:59
select cron.schedule('poll-disclosures-early', '* 22-23 * * 0-4', $$select public.invoke_poll_disclosures()$$);
-- KST 월~금 09:00~19:59  = UTC 월~금 00:00~10:59
select cron.schedule('poll-disclosures-day',   '* 0-10 * * 1-5',  $$select public.invoke_poll_disclosures()$$);
-- 그 외 시간(밤·주말)은 30분마다
select cron.schedule('poll-disclosures-night', '*/30 * * * *',    $$select public.invoke_poll_disclosures()$$);

-- 확인:  select * from cron.job;
-- 실행 기록:  select * from cron.job_run_details order by start_time desc limit 20;
-- 멈추기:  select cron.unschedule('poll-disclosures-day');
