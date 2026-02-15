-- schema.sql
-- Local Docker Postgres 기준 스키마
-- 전략: talk_detail에 매칭 실패 토큰도 row로 저장하되, url_path/vector는 NULL 허용

BEGIN;

-- 필요 시 주석 해제(세션 타임존 고정)
-- SET TIME ZONE 'Asia/Seoul';

CREATE TABLE IF NOT EXISTS member (
    member_no INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id VARCHAR(50) NOT NULL UNIQUE,
    passwd VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    mobile_phone VARCHAR(20) NOT NULL,
    e_mail_address VARCHAR NOT NULL,
    deaf_muteness_section_code BOOLEAN NOT NULL DEFAULT TRUE,
    create_user VARCHAR(50) NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'),
    update_user VARCHAR(50),
    update_date TIMESTAMP WITHOUT TIME ZONE,
    delete_user VARCHAR(50),
    delete_date TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE IF NOT EXISTS talk_room (
    talk_room_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_no1 INTEGER NOT NULL,
    member_no2 INTEGER NOT NULL,
    create_user VARCHAR(50) NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'),
    update_user VARCHAR(50),
    update_date TIMESTAMP WITHOUT TIME ZONE,
    delete_user VARCHAR(50),
    delete_date TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT fk_talk_room_member_no1 FOREIGN KEY (member_no1) REFERENCES member(member_no),
    CONSTRAINT fk_talk_room_member_no2 FOREIGN KEY (member_no2) REFERENCES member(member_no)
);

CREATE TABLE IF NOT EXISTS talk (
    talk_room_id INTEGER NOT NULL,
    member_no INTEGER NOT NULL,
    talk_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    message VARCHAR NOT NULL,
    create_user VARCHAR(50) NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'),
    update_user VARCHAR(50),
    update_date TIMESTAMP WITHOUT TIME ZONE,
    delete_user VARCHAR(50),
    delete_date TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT pk_talk PRIMARY KEY (talk_room_id, member_no, talk_date),
    CONSTRAINT fk_talk_room FOREIGN KEY (talk_room_id) REFERENCES talk_room(talk_room_id),
    CONSTRAINT fk_talk_member FOREIGN KEY (member_no) REFERENCES member(member_no)
);

CREATE TABLE IF NOT EXISTS corpus (
    word_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    word_name VARCHAR NOT NULL UNIQUE,
    url_path VARCHAR,
    vector TEXT,
    create_user VARCHAR(50) NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'),
    update_user VARCHAR(50),
    update_date TIMESTAMP WITHOUT TIME ZONE,
    delete_user VARCHAR(50),
    delete_date TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE IF NOT EXISTS talk_detail (
    talk_room_id INTEGER NOT NULL,
    member_no INTEGER NOT NULL,

    -- talk_detail은 반드시 어떤 talk에 속하는지 식별되어야 하므로 NOT NULL 유지
    talk_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,

    -- tail_date는 generated column: talk_date를 그대로 저장(INSERT 금지)
    tail_date TIMESTAMP WITHOUT TIME ZONE GENERATED ALWAYS AS (talk_date) STORED,

    word_order_no SMALLINT NOT NULL,
    word_name VARCHAR NOT NULL,

    -- ✅ 실패 매칭 토큰도 row로 저장하기 위해 NULL 허용
    url_path VARCHAR,
    vector TEXT,

    create_user VARCHAR(50) NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'),
    update_user VARCHAR(50),
    update_date TIMESTAMP WITHOUT TIME ZONE,
    delete_user VARCHAR(50),
    delete_date TIMESTAMP WITHOUT TIME ZONE,

    CONSTRAINT pk_talk_detail PRIMARY KEY (talk_room_id, member_no, talk_date, word_order_no),
    CONSTRAINT fk_talk_detail_talk FOREIGN KEY (talk_room_id, member_no, talk_date)
        REFERENCES talk(talk_room_id, member_no, talk_date),
    CONSTRAINT fk_talk_detail_member FOREIGN KEY (member_no) REFERENCES member(member_no)
);

COMMIT;
