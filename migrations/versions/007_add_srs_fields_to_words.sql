-- ============================================
-- 迁移脚本: 007_add_srs_fields_to_words.sql
-- 描述: 给 words 添加间隔重复(SM-2)调度字段
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 007
-- 说明:
--   ef              易学度因子 (Easiness Factor)，初始 2.5
--   review_interval 间隔天数 (上次到下次复习的天数)
--   repetitions     连续答对次数
--   next_review_at  下次应复习时间（NULL 或已过 = 到期）
--   last_reviewed_at 上次复习时间
-- ============================================

-- 执行迁移
ALTER TABLE words ADD COLUMN ef FLOAT NOT NULL DEFAULT 2.5;
ALTER TABLE words ADD COLUMN review_interval INT NOT NULL DEFAULT 0;
ALTER TABLE words ADD COLUMN repetitions INT NOT NULL DEFAULT 0;
ALTER TABLE words ADD COLUMN next_review_at DATETIME NULL;
ALTER TABLE words ADD COLUMN last_reviewed_at DATETIME NULL;

-- 创建索引（按用户+到期时间查询复习队列）
CREATE INDEX idx_words_next_review ON words(user_id, next_review_at);

-- ============================================
-- 回滚脚本
-- ALTER TABLE words DROP INDEX idx_words_next_review;
-- ALTER TABLE words DROP COLUMN last_reviewed_at;
-- ALTER TABLE words DROP COLUMN next_review_at;
-- ALTER TABLE words DROP COLUMN repetitions;
-- ALTER TABLE words DROP COLUMN review_interval;
-- ALTER TABLE words DROP COLUMN ef;
-- ============================================