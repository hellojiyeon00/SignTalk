-- verify.sql

-- 1) row count
SELECT 'member' AS table, COUNT(*) FROM public.member
UNION ALL SELECT 'talk_room', COUNT(*) FROM public.talk_room
UNION ALL SELECT 'corpus', COUNT(*) FROM public.corpus
UNION ALL SELECT 'talk', COUNT(*) FROM public.talk
UNION ALL SELECT 'talk_detail', COUNT(*) FROM public.talk_detail;

-- 2) talk ↔ talk_detail 조인 전체(2개 메시지)
SELECT
  t.talk_room_id,
  t.member_no,
  t.talk_date,
  t.message,
  td.word_order_no,
  td.word_name,
  td.url_path,
  td.vector,
  td.tail_date
FROM public.talk t
LEFT JOIN public.talk_detail td
  ON td.talk_room_id = t.talk_room_id
 AND td.member_no    = t.member_no
 AND td.talk_date    = t.talk_date
WHERE t.talk_room_id = 1
ORDER BY t.talk_date, td.word_order_no;

-- 3) 실패(NULL) 토큰만 보기
SELECT
  talk_room_id, member_no, talk_date, word_order_no, word_name, url_path, vector
FROM public.talk_detail
WHERE talk_room_id = 1
  AND (url_path IS NULL OR vector IS NULL)
ORDER BY talk_date, word_order_no;
