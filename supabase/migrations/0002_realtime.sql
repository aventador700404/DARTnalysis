-- 새 공시가 들어오면 브라우저로 바로 푸시 (Supabase Realtime)
-- Supabase 프로젝트에서만 실행 (supabase_realtime publication은 Supabase가 만들어 둠)
alter publication supabase_realtime add table public.disclosures;
alter publication supabase_realtime add table public.disclosure_impacts;
