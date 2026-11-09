-- =========================================================
-- 网球约球 MVP 初始化（MySQL 8.0.16+ / 微信云托管 MySQL 8.0）
-- 对应：apps/api/migrations/sql/0001_init.sql（由 Alembic 0001 迁移执行）
-- 已在本地 MySQL 8.0.46 上验证（含负向用例，见 DESIGN.md §5.6）
--
-- 约定
--   * 字符集 utf8mb4 / utf8mb4_0900_ai_ci；引擎 InnoDB
--   * 所有 DATETIME(3) 存 UTC：应用连接建立后执行 SET time_zone = '+00:00'
--     （CURRENT_TIMESTAMP(3) / ON UPDATE 随会话时区取值）
--   * 枚举一律 TINYINT 码 + CHECK，不用 ENUM
--   * 主键 BIGINT UNSIGNED AUTO_INCREMENT，API 层以字符串输出
--   * 外键不使用 CASCADE / SET NULL（MySQL 禁止在 CHECK 引用列、
--     存储生成列的基列上使用外键参照动作）
-- =========================================================
-- 建库在控制台或本地 compose 中完成（utf8mb4 / utf8mb4_0900_ai_ci）。
-- 迁移脚本在当前库执行，不切换数据库。
-- =========================================================
-- 1. 用户 app_user
--   gender: 1男 2女
--   style_mask: 位掩码 1=singles 2=doubles 4=casual 8=competitive（可多选）
-- =========================================================
CREATE TABLE app_user (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  openid            VARCHAR(64)  NOT NULL,
  unionid           VARCHAR(64)  NULL,
  nickname          VARCHAR(64)  NULL,                 -- 完善资料前可为空
  avatar_file_id    VARCHAR(512) NULL,                 -- 云托管对象存储 fileID（cloud://...）
  ntrp              DECIMAL(2,1) NULL,
  gender            TINYINT UNSIGNED NULL,
  age               TINYINT UNSIGNED NULL,
  city              VARCHAR(32)  NULL,
  style_mask        TINYINT UNSIGNED NOT NULL DEFAULT 0,
  bio               VARCHAR(500) NULL,
  confirm_count     INT NOT NULL DEFAULT 0,            -- 完成并提交评分的场次
  cancel_count      INT NOT NULL DEFAULT 0,            -- 匹配成功后主动取消/退出次数
  credit_score      INT AS (GREATEST(confirm_count - cancel_count, 0)) STORED,
  rating_sum        INT NOT NULL DEFAULT 0,
  rating_count      INT NOT NULL DEFAULT 0,
  avg_rating        DECIMAL(3,2) AS (CASE WHEN rating_count > 0
                                          THEN ROUND(rating_sum / rating_count, 2) END) STORED,
  ntrp_update_time  DATETIME(3) NULL,                  -- 上次「修改」NTRP 的时间（首次设置不计）
  profile_completed BOOLEAN NOT NULL DEFAULT FALSE,
  last_login_time   DATETIME(3) NULL,
  version           INT NOT NULL DEFAULT 0,
  create_time       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  is_deleted        BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  UNIQUE KEY uq_app_user_openid (openid),
  KEY idx_app_user_city_ntrp (city, ntrp),
  KEY idx_app_user_credit (credit_score),
  CONSTRAINT ck_app_user_ntrp   CHECK (ntrp IS NULL OR (ntrp BETWEEN 1.0 AND 7.0 AND MOD(ntrp * 10, 5) = 0)),
  CONSTRAINT ck_app_user_gender CHECK (gender IS NULL OR gender IN (1, 2)),
  CONSTRAINT ck_app_user_age    CHECK (age IS NULL OR age BETWEEN 6 AND 99),
  CONSTRAINT ck_app_user_style  CHECK (style_mask BETWEEN 0 AND 15),
  CONSTRAINT ck_app_user_counts CHECK (confirm_count >= 0 AND cancel_count >= 0
                                       AND rating_sum >= 0 AND rating_count >= 0),
  CONSTRAINT ck_app_user_profile CHECK (
    profile_completed = FALSE
    OR (nickname IS NOT NULL AND avatar_file_id IS NOT NULL AND ntrp IS NOT NULL
        AND gender IS NOT NULL AND age IS NOT NULL AND city IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 2. 球场 court（仅内置，用户不可新增）
-- =========================================================
CREATE TABLE court (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name         VARCHAR(100) NOT NULL,
  city         VARCHAR(32)  NOT NULL,
  district     VARCHAR(32)  NULL,
  address      VARCHAR(255) NOT NULL,
  latitude     DECIMAL(9,6) NULL,
  longitude    DECIMAL(9,6) NULL,
  sort_order   INT NOT NULL DEFAULT 0,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  create_time  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
  -- 部分唯一索引替代：未删除行才参与 (city, name) 唯一
  active_name  VARCHAR(100) AS (CASE WHEN is_deleted = FALSE THEN name END) STORED,
  PRIMARY KEY (id),
  UNIQUE KEY uq_court_city_active_name (city, active_name),
  KEY idx_court_city (city, is_deleted, is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 3. 约球需求 match_request
--   status       : 1待匹配 2已匹配 3已完成 4已取消
--   match_type   : 1单打 2双打
--   slots_needed : 需招募搭档人数（不含发布者）；单打=1，双打 1~3
--   cancel_reason: 1发布方匹配前取消 2发布方匹配后取消 3搭档退出导致取消
--                  4未满员到期 5超时未全员到场
--   gender_pref  : 0不限 1男 2女
-- =========================================================
CREATE TABLE match_request (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  publisher_id       BIGINT UNSIGNED NOT NULL,
  court_id           BIGINT UNSIGNED NOT NULL,
  city               VARCHAR(32) NOT NULL,             -- 冗余自 court.city
  match_date         DATE NOT NULL,                    -- 北京时间的开始日期
  time_slot          CHAR(11) NOT NULL,                -- 'HH:MM-HH:MM'；结束钟点不晚于开始时表示次日结束
  start_at           DATETIME(3) NOT NULL,             -- UTC，由 match_date + 开始钟点 @Asia/Shanghai 计算
  end_at             DATETIME(3) NOT NULL,             -- UTC；可落到开始日的次日。时长 30 分钟～8 小时由写入校验保证
  match_type         TINYINT UNSIGNED NOT NULL,
  slots_needed       TINYINT UNSIGNED NOT NULL,
  filled_count       TINYINT UNSIGNED NOT NULL DEFAULT 0,
  expected_ntrp_min  DECIMAL(2,1) NULL,
  expected_ntrp_max  DECIMAL(2,1) NULL,
  gender_pref        TINYINT UNSIGNED NOT NULL DEFAULT 0,
  status             TINYINT UNSIGNED NOT NULL DEFAULT 1,
  cancel_reason      TINYINT UNSIGNED NULL,
  cancelled_by       BIGINT UNSIGNED NULL,
  matched_time       DATETIME(3) NULL,
  completed_time     DATETIME(3) NULL,
  cancelled_time     DATETIME(3) NULL,
  version            INT NOT NULL DEFAULT 0,
  create_time        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  is_deleted         BOOLEAN NOT NULL DEFAULT FALSE,
  -- 部分唯一索引替代：同一发布者同时仅一个进行中（待匹配/已匹配）约球
  active_publisher_id BIGINT UNSIGNED AS (
    CASE WHEN status IN (1, 2) AND is_deleted = FALSE THEN publisher_id END) STORED,
  PRIMARY KEY (id),
  UNIQUE KEY uq_mr_one_active_per_publisher (active_publisher_id),
  KEY idx_mr_recommend  (city, status, match_date, start_at),
  KEY idx_mr_court_date (court_id, match_date, time_slot),
  KEY idx_mr_publisher  (publisher_id, status, create_time),
  KEY idx_mr_sched      (status, start_at),
  CONSTRAINT fk_mr_publisher FOREIGN KEY (publisher_id) REFERENCES app_user (id),
  CONSTRAINT fk_mr_court     FOREIGN KEY (court_id)     REFERENCES court (id),
  CONSTRAINT fk_mr_cancelled_by FOREIGN KEY (cancelled_by) REFERENCES app_user (id),
  CONSTRAINT ck_mr_status       CHECK (status IN (1, 2, 3, 4)),
  CONSTRAINT ck_mr_match_type   CHECK (match_type IN (1, 2)),
  CONSTRAINT ck_mr_slots        CHECK ((match_type = 1 AND slots_needed = 1)
                                    OR (match_type = 2 AND slots_needed BETWEEN 1 AND 3)),
  CONSTRAINT ck_mr_filled       CHECK (filled_count <= slots_needed),
  CONSTRAINT ck_mr_matched_full CHECK (status NOT IN (2, 3) OR filled_count = slots_needed),
  CONSTRAINT ck_mr_time_slot    CHECK (REGEXP_LIKE(time_slot,
      '^([01][0-9]|2[0-3]):[0-5][0-9]-([01][0-9]|2[0-3]):[0-5][0-9]$', 'c')),
  CONSTRAINT ck_mr_time_order   CHECK (end_at > start_at),
  CONSTRAINT ck_mr_gender_pref  CHECK (gender_pref IN (0, 1, 2)),
  CONSTRAINT ck_mr_ntrp_range   CHECK (
        (expected_ntrp_min IS NULL OR expected_ntrp_min BETWEEN 1.0 AND 7.0)
    AND (expected_ntrp_max IS NULL OR expected_ntrp_max BETWEEN 1.0 AND 7.0)
    AND (expected_ntrp_min IS NULL OR expected_ntrp_max IS NULL OR expected_ntrp_min <= expected_ntrp_max)),
  CONSTRAINT ck_mr_cancel_reason CHECK (cancel_reason IS NULL OR cancel_reason BETWEEN 1 AND 5),
  CONSTRAINT ck_mr_cancel_consistency CHECK ((status = 4) = (cancel_reason IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 4. 申请记录 application
--   status      : 1待处理 2已同意 3已拒绝 4已取消
--   close_reason: 1发布方拒绝 2名额已满自动拒绝 3申请方撤回 4约球被取消/过期 5搭档本人退出
-- =========================================================
CREATE TABLE application (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  request_id    BIGINT UNSIGNED NOT NULL,
  applicant_id  BIGINT UNSIGNED NOT NULL,
  status        TINYINT UNSIGNED NOT NULL DEFAULT 1,
  close_reason  TINYINT UNSIGNED NULL,
  handle_time   DATETIME(3) NULL,
  version       INT NOT NULL DEFAULT 0,
  create_time   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),   -- 即 applyTime
  update_time   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_application_req_applicant (request_id, applicant_id),
  KEY idx_app_applicant (applicant_id, status, create_time),
  KEY idx_app_request   (request_id, status),
  CONSTRAINT fk_app_request   FOREIGN KEY (request_id)   REFERENCES match_request (id),
  CONSTRAINT fk_app_applicant FOREIGN KEY (applicant_id) REFERENCES app_user (id),
  CONSTRAINT ck_app_status       CHECK (status IN (1, 2, 3, 4)),
  CONSTRAINT ck_app_close_reason CHECK (close_reason IS NULL OR close_reason BETWEEN 1 AND 5),
  CONSTRAINT ck_app_close_consistency CHECK ((status IN (3, 4)) = (close_reason IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 5. 参与者 / 到场 match_participant（1:N）
--   role: 1发布者 2搭档；status: 1有效 2已退出
-- =========================================================
CREATE TABLE match_participant (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  request_id      BIGINT UNSIGNED NOT NULL,
  user_id         BIGINT UNSIGNED NOT NULL,
  role            TINYINT UNSIGNED NOT NULL,
  application_id  BIGINT UNSIGNED NULL,
  status          TINYINT UNSIGNED NOT NULL DEFAULT 1,
  arrived         BOOLEAN NOT NULL DEFAULT FALSE,
  arrived_time    DATETIME(3) NULL,
  rated           BOOLEAN NOT NULL DEFAULT FALSE,     -- 已提交对其他所有参与者的评分
  rated_time      DATETIME(3) NULL,
  left_time       DATETIME(3) NULL,
  version         INT NOT NULL DEFAULT 0,
  create_time     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  -- 部分唯一索引替代：每个约球仅一名发布者
  publisher_request_id BIGINT UNSIGNED AS (CASE WHEN role = 1 THEN request_id END) STORED,
  PRIMARY KEY (id),
  UNIQUE KEY uq_participant_req_user (request_id, user_id),
  UNIQUE KEY uq_participant_publisher (publisher_request_id),
  KEY idx_participant_user (user_id, status),
  CONSTRAINT fk_participant_request FOREIGN KEY (request_id)     REFERENCES match_request (id),
  CONSTRAINT fk_participant_user    FOREIGN KEY (user_id)        REFERENCES app_user (id),
  CONSTRAINT fk_participant_app     FOREIGN KEY (application_id) REFERENCES application (id),
  CONSTRAINT ck_participant_role    CHECK (role IN (1, 2)),
  CONSTRAINT ck_participant_status  CHECK (status IN (1, 2)),
  CONSTRAINT ck_participant_app     CHECK ((role = 1) = (application_id IS NULL)),
  CONSTRAINT ck_participant_arrived CHECK (arrived = (arrived_time IS NOT NULL)),
  CONSTRAINT ck_participant_rated   CHECK (rated = (rated_time IS NOT NULL)),
  CONSTRAINT ck_participant_rate_after_arrive CHECK (rated = FALSE OR arrived = TRUE),
  CONSTRAINT ck_participant_left    CHECK ((status = 2) = (left_time IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 6. 评分 match_rating（两两互评，只追加）
-- =========================================================
CREATE TABLE match_rating (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  request_id   BIGINT UNSIGNED NOT NULL,
  rater_id     BIGINT UNSIGNED NOT NULL,
  ratee_id     BIGINT UNSIGNED NOT NULL,
  score        TINYINT UNSIGNED NOT NULL,
  create_time  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_rating (request_id, rater_id, ratee_id),
  KEY idx_rating_ratee (ratee_id),
  KEY idx_rating_rater (rater_id, request_id),
  CONSTRAINT fk_rating_request FOREIGN KEY (request_id) REFERENCES match_request (id),
  CONSTRAINT fk_rating_rater   FOREIGN KEY (rater_id)   REFERENCES app_user (id),
  CONSTRAINT fk_rating_ratee   FOREIGN KEY (ratee_id)   REFERENCES app_user (id),
  CONSTRAINT ck_rating_score CHECK (score BETWEEN 1 AND 5),
  CONSTRAINT ck_rating_self  CHECK (rater_id <> ratee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 7. LLM 匹配缓存 llm_match_cache
-- =========================================================
CREATE TABLE llm_match_cache (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  publisher_id    BIGINT UNSIGNED NOT NULL,
  candidate_id    BIGINT UNSIGNED NOT NULL,
  input_hash      CHAR(64) NOT NULL,      -- sha256(双方输入字段 + 期望条件 + prompt_version + model)
  llm_score       TINYINT UNSIGNED NOT NULL,
  reason          VARCHAR(100) NULL,
  model_name      VARCHAR(64) NOT NULL,
  prompt_version  VARCHAR(16) NOT NULL,
  expire_time     DATETIME(3) NOT NULL,
  create_time     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_llm_cache_pair (publisher_id, candidate_id),
  KEY idx_llm_cache_candidate (candidate_id),
  KEY idx_llm_cache_expire (expire_time),
  CONSTRAINT fk_llm_cache_publisher FOREIGN KEY (publisher_id) REFERENCES app_user (id),
  CONSTRAINT fk_llm_cache_candidate FOREIGN KEY (candidate_id) REFERENCES app_user (id),
  CONSTRAINT ck_llm_cache_score CHECK (llm_score BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- LLM 每日调用计数（限额）
CREATE TABLE llm_usage_daily (
  usage_date       DATE NOT NULL,          -- 北京时间日期
  scope            VARCHAR(64) NOT NULL,   -- 'global' | 'user:<id>'
  call_count       INT NOT NULL DEFAULT 0,
  candidate_count  INT NOT NULL DEFAULT 0,
  update_time      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (usage_date, scope),
  CONSTRAINT ck_llm_usage_counts CHECK (call_count >= 0 AND candidate_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =========================================================
-- 8. 状态迁移日志 state_transition_log（只追加）
-- =========================================================
CREATE TABLE state_transition_log (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entity_type    VARCHAR(32) NOT NULL,    -- match_request / application / match_participant / user_credit
  entity_id      BIGINT UNSIGNED NOT NULL,
  request_id     BIGINT UNSIGNED NULL,
  action         VARCHAR(32) NOT NULL,    -- publish/apply/agree/reject/withdraw/cancel/leave/arrive/complete/rate/expire/auto_cancel/confirm_inc/cancel_inc
  from_status    TINYINT UNSIGNED NULL,
  to_status      TINYINT UNSIGNED NULL,
  operator_type  TINYINT UNSIGNED NOT NULL,  -- 1用户 2系统
  operator_id    BIGINT UNSIGNED NULL,
  detail         JSON NULL,
  create_time    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_stl_entity  (entity_type, entity_id, create_time),
  KEY idx_stl_request (request_id, create_time),
  CONSTRAINT ck_stl_operator CHECK (operator_type IN (1, 2) AND (operator_type = 2 OR operator_id IS NOT NULL)),
  CONSTRAINT ck_stl_detail   CHECK (detail IS NULL OR JSON_TYPE(detail) = 'OBJECT')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
