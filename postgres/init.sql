-- 볼륨 날렸을 때 보험처리

CREATE SCHEMA IF NOT EXISTS multicampus_schema;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ────────────────────────────────────────────────────────────────
-- member
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.member (
    member_no                  SERIAL          PRIMARY KEY,
    member_id                  VARCHAR(50)     NOT NULL UNIQUE,
    passwd                     TEXT            NOT NULL,
    full_name                  VARCHAR         NOT NULL,
    mobile_phone               VARCHAR(50)     NOT NULL,
    e_mail_address             VARCHAR         NOT NULL,
    deaf_muteness_section_code BOOLEAN         NOT NULL DEFAULT TRUE,
    create_user                VARCHAR(50)     NOT NULL,
    create_date                TIMESTAMP       NOT NULL DEFAULT NOW(),
    update_user                VARCHAR(50),
    update_date                TIMESTAMP,
    delete_user                VARCHAR(50),
    delete_date                TIMESTAMP
);

-- ────────────────────────────────────────────────────────────────
-- talk_room
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.talk_room (
    talk_room_id  SERIAL      PRIMARY KEY,
    member_no1    INTEGER     NOT NULL,
    member_no2    INTEGER     NOT NULL,
    create_user   VARCHAR(50) NOT NULL,
    create_date   TIMESTAMP   NOT NULL DEFAULT NOW(),
    update_user   VARCHAR(50),
    update_date   TIMESTAMP,
    delete_user   VARCHAR(50),
    delete_date   TIMESTAMP
);

-- ────────────────────────────────────────────────────────────────
-- talk
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.talk (
    talk_room_id  INTEGER      NOT NULL,
    member_no     INTEGER      NOT NULL,
    talk_date     TIMESTAMP    NOT NULL,
    message       TEXT         NOT NULL,
    confirm_yn    CHAR(1)      NOT NULL DEFAULT 'N',
    create_user   VARCHAR(50)  NOT NULL,
    create_date   TIMESTAMP    NOT NULL DEFAULT NOW(),
    update_user   VARCHAR(50),
    update_date   TIMESTAMP,
    delete_user   VARCHAR(50),
    delete_date   TIMESTAMP,
    PRIMARY KEY (talk_room_id, member_no, talk_date)
);

-- ────────────────────────────────────────────────────────────────
-- talk_detail
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.talk_detail (
    talk_room_id   INTEGER      NOT NULL,
    member_no      INTEGER      NOT NULL,
    talk_date      TIMESTAMP    NOT NULL,
    word_order_no  SMALLINT     NOT NULL,
    word_name      VARCHAR      NOT NULL,
    url_path       VARCHAR      NOT NULL,
    vector         TEXT         NOT NULL,
    create_user    VARCHAR(50)  NOT NULL,
    create_date    TIMESTAMP    NOT NULL DEFAULT NOW(),
    update_user    VARCHAR(50),
    update_date    TIMESTAMP,
    delete_user    VARCHAR(50),
    delete_date    TIMESTAMP,
    PRIMARY KEY (talk_room_id, member_no, talk_date, word_order_no)
);

-- ────────────────────────────────────────────────────────────────
-- characters
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.characters (
    character_id           INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    character_type_code    VARCHAR(2)  NOT NULL,
    character_content      TEXT        NOT NULL,
    disaster_sn            INTEGER,
    disaster_crt_dt        TIMESTAMP,
    disaster_rcptn_rgn_nm  VARCHAR,
    disaster_emrg_step_nm  VARCHAR,
    disaster_dst_se_nm     VARCHAR,
    disaster_reg_ymd       VARCHAR(8),
    disaster_mdfcn_ymd     VARCHAR(8),
    create_user            VARCHAR(50) NOT NULL,
    create_date            TIMESTAMP   NOT NULL DEFAULT NOW(),
    update_date            TIMESTAMP,
    delete_user            VARCHAR(50),
    delete_date            TIMESTAMP
);

-- ────────────────────────────────────────────────────────────────
-- characters_send
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS multicampus_schema.characters_send (
    character_id  INTEGER     NOT NULL,
    member_no     INTEGER     NOT NULL,
    send_date     TIMESTAMP   NOT NULL,
    create_user   VARCHAR(50) NOT NULL,
    create_date   TIMESTAMP   NOT NULL DEFAULT NOW(),
    update_user   VARCHAR(50),
    update_date   TIMESTAMP,
    delete_user   VARCHAR(50),
    PRIMARY KEY (character_id, member_no)
);

-- corpus 테이블 (최초 초기화 시 자동 생성)
CREATE TABLE IF NOT EXISTS multicampus_schema.corpus (
    word_id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    word_name              VARCHAR     NOT NULL,
    url_path               VARCHAR     NOT NULL,
    vector                 TEXT        NOT NULL,
    meaning_classification VARCHAR,
    create_user            VARCHAR(50) NOT NULL,
    create_date            TIMESTAMP   NOT NULL DEFAULT NOW(),
    update_user            VARCHAR(50),
    update_date            TIMESTAMP,
    delete_user            VARCHAR(50),
    delete_date            TIMESTAMP
);

-- corpus CSV 임포트 (스테이징 경유 — 천 단위 쉼표 & identity 컬럼 처리)
CREATE TEMP TABLE corpus_staging (
    word_id                TEXT,
    word_name              TEXT,
    url_path               TEXT,
    vector                 TEXT,
    create_user            TEXT,
    create_date            TEXT,
    update_user            TEXT,
    update_date            TEXT,
    delete_user            TEXT,
    delete_date            TEXT,
    meaning_classification TEXT
);

\COPY corpus_staging FROM '/docker-entrypoint-initdb.d/corpus.csv' CSV HEADER;

INSERT INTO multicampus_schema.corpus
    (word_id, word_name, url_path, vector, meaning_classification,
     create_user, create_date, update_user, update_date, delete_user, delete_date)
OVERRIDING SYSTEM VALUE
SELECT
    REPLACE(word_id, ',', '')::INTEGER,
    word_name,
    url_path,
    vector,
    NULLIF(meaning_classification, ''),
    create_user,
    NOW(),
    NULLIF(update_user, ''),
    CASE WHEN update_date = '' THEN NULL ELSE NOW() END,
    NULLIF(delete_user, ''),
    NULL
FROM corpus_staging
ON CONFLICT (word_id) DO NOTHING;
