-- seed.sql
-- 최소 E2E + 새로고침(히스토리) 복원 테스트용 시드 데이터
-- 대상 테이블: member / talk_room / corpus / talk / talk_detail
-- 전략:
-- - member_no, talk_room_id, word_id는 GENERATED ALWAYS AS IDENTITY → OVERRIDING SYSTEM VALUE 사용
-- - talk_detail.tail_date는 GENERATED ALWAYS (talk_date) → INSERT 금지
-- - talk_detail.url_path/vector는 NULL 허용(매칭 실패 토큰 row 저장)

BEGIN;

-- 1) member: 일반인 1명 + 농인 1명
INSERT INTO member (
  member_no, member_id, passwd, full_name, mobile_phone, e_mail_address,
  deaf_muteness_section_code, create_user, create_date
)
OVERRIDING SYSTEM VALUE
VALUES
  (1, 'user_general', 'pw1234', '일반인_테스터', '01011112222', 'general@test.com',
   FALSE, 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (2, 'user_deaf', 'pw1234', '농인_테스터', '01033334444', 'deaf@test.com',
   TRUE, 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (member_no) DO NOTHING;

-- 2) talk_room: 대화방 1개 (일반인=1, 농인=2)
INSERT INTO talk_room (
  talk_room_id, member_no1, member_no2,
  create_user, create_date
)
OVERRIDING SYSTEM VALUE
VALUES
  (1, 1, 2, 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (talk_room_id) DO NOTHING;

-- 3) corpus: 단어 10개
-- vector는 TEXT라서 임시로 '{}' 형태 문자열을 넣어둠(실서비스 벡터로 교체 가능)
INSERT INTO corpus (
  word_id, word_name, url_path, vector,
  create_user, create_date
)
OVERRIDING SYSTEM VALUE
VALUES
  (1,  '안녕하세요', '/videos/hello.mp4',      '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (2,  '오늘',     '/videos/today.mp4',      '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (3,  '날씨',     '/videos/weather.mp4',    '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (4,  '춥다',     '/videos/cold.mp4',       '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (5,  '따뜻',     '/videos/warm.mp4',       '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (6,  '점심',     '/videos/lunch.mp4',      '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (7,  '먹다',     '/videos/eat.mp4',        '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (8,  '좋다',     '/videos/good.mp4',       '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (9,  '감사',     '/videos/thanks.mp4',     '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (10, '미안',     '/videos/sorry.mp4',      '{}', 'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (word_id) DO NOTHING;

-- 4) talk: 대화 2건 (서로 다른 talk_date)
-- 4-1) 일반인 → 농인
INSERT INTO talk (
  talk_room_id, member_no, talk_date, message,
  create_user, create_date
)
VALUES
  (1, 1, '2026-02-15 13:00:00',
   '안녕하세요. 오늘 날씨가 정말 좋네요. 저는 점심으로 KFC를 먹었어요.',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (talk_room_id, member_no, talk_date) DO NOTHING;

-- 4-2) 농인 → 일반인
INSERT INTO talk (
  talk_room_id, member_no, talk_date, message,
  create_user, create_date
)
VALUES
  (1, 2, '2026-02-15 13:05:00',
   '안녕하세요. 오늘은 조금 춥지만 저는 괜찮아요.',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (talk_room_id, member_no, talk_date) DO NOTHING;

-- 5) talk_detail: 토큰 단위 저장
-- 주의:
-- - talk_detail.talk_date는 NOT NULL → 반드시 INSERT
-- - talk_detail.tail_date는 생성 컬럼 → INSERT 대상에서 제외

-- 5-1) 일반인 메시지 토큰 (5 성공 + 1 실패)
INSERT INTO talk_detail (
  talk_room_id, member_no, talk_date, word_order_no,
  word_name, url_path, vector,
  create_user, create_date
)
VALUES
  (1, 1, '2026-02-15 13:00:00', 1, '안녕하세요', '/videos/hello.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 1, '2026-02-15 13:00:00', 2, '오늘', '/videos/today.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 1, '2026-02-15 13:00:00', 3, '좋다', '/videos/good.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 1, '2026-02-15 13:00:00', 4, '점심', '/videos/lunch.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 1, '2026-02-15 13:00:00', 5, '먹다', '/videos/eat.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  -- 실패 매칭
  (1, 1, '2026-02-15 13:00:00', 6, 'KFC', NULL, NULL,
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (talk_room_id, member_no, talk_date, word_order_no) DO NOTHING;

-- 5-2) 농인 메시지 토큰 (3 성공 + 1 실패)
-- '괜찮다'는 corpus에 없다고 가정(실패 토큰)
INSERT INTO talk_detail (
  talk_room_id, member_no, talk_date, word_order_no,
  word_name, url_path, vector,
  create_user, create_date
)
VALUES
  (1, 2, '2026-02-15 13:05:00', 1, '안녕하세요', '/videos/hello.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 2, '2026-02-15 13:05:00', 2, '오늘', '/videos/today.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  (1, 2, '2026-02-15 13:05:00', 3, '춥다', '/videos/cold.mp4', '{}',
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')),
  -- 실패 매칭
  (1, 2, '2026-02-15 13:05:00', 4, '괜찮다', NULL, NULL,
   'seed', (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'))
ON CONFLICT (talk_room_id, member_no, talk_date, word_order_no) DO NOTHING;

COMMIT;
