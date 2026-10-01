-- Edge Function이 호출 수를 누적 기록할 때 쓰는 함수 (같은 날·같은 API면 더하기)
create or replace function public.bump_api_usage(p_day date, p_api text, p_calls int)
returns void language sql security definer set search_path = public as $$
  insert into public.api_usage (day, api, calls) values (p_day, p_api, p_calls)
  on conflict (day, api) do update set calls = public.api_usage.calls + excluded.calls;
$$;
revoke all on function public.bump_api_usage(date, text, int) from public, anon, authenticated;
