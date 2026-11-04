-- =========================================================
-- MySQL 最小权限账号（以 root 在「数据库管理」/ SQL 窗口执行一次）
-- 云托管 MySQL 控制台最多 3 个账号：root + tennis_migrator + tennis_app
-- 密码由控制台/密码管理器生成，不入库、不进 Git
-- =========================================================
CREATE USER IF NOT EXISTS 'tennis_migrator'@'%' IDENTIFIED BY '<MIGRATOR_PASSWORD>';
CREATE USER IF NOT EXISTS 'tennis_app'@'%'      IDENTIFIED BY '<APP_PASSWORD>';

-- 迁移账号：仅 tennis 库的 DDL+DML（Alembic 使用）
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
  ON tennis.* TO 'tennis_migrator'@'%';

-- 运行时账号：只有 DML，且按表授予；日志/评分表只读+追加
GRANT SELECT, INSERT, UPDATE, DELETE ON tennis.app_user          TO 'tennis_app'@'%';
GRANT SELECT                         ON tennis.court             TO 'tennis_app'@'%';
GRANT SELECT, INSERT, UPDATE         ON tennis.match_request     TO 'tennis_app'@'%';
GRANT SELECT, INSERT, UPDATE         ON tennis.application       TO 'tennis_app'@'%';
GRANT SELECT, INSERT, UPDATE         ON tennis.match_participant TO 'tennis_app'@'%';
GRANT SELECT, INSERT                 ON tennis.match_rating      TO 'tennis_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON tennis.llm_match_cache   TO 'tennis_app'@'%';
GRANT SELECT, INSERT, UPDATE         ON tennis.llm_usage_daily   TO 'tennis_app'@'%';
GRANT SELECT, INSERT                 ON tennis.state_transition_log TO 'tennis_app'@'%';
GRANT SELECT                         ON tennis.alembic_version   TO 'tennis_app'@'%';
-- 注意：GET_LOCK/RELEASE_LOCK 不需要额外权限
