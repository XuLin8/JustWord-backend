-- ============================================
-- 迁移脚本: 016_add_progress_models.sql
-- 描述: 进度后端化 + 统一统计 数据底座
--   1) learning_records 增加 response_ms / is_new
--   2) 新增 user_preferences / daily_stats / word_snapshots
-- 日期: 2026-08-25
-- 版本: 016
-- ============================================

-- learning_records 增强（可空字段，兼容旧数据）
ALTER TABLE learning_records
    ADD COLUMN response_ms INT NULL COMMENT '该次判定反应耗时(毫秒)' AFTER score,
    ADD COLUMN is_new TINYINT NULL COMMENT '判定时是否新学(1)/复习(0)' AFTER response_ms;

-- 用户偏好
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(36) NOT NULL,
    recitation_rule VARCHAR(20) NOT NULL DEFAULT 'judge',
    daily_target INT NOT NULL DEFAULT 20,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_pref_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 每日聚合统计
CREATE TABLE IF NOT EXISTS daily_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    learning_date DATE NOT NULL,
    distinct_words INT NOT NULL DEFAULT 0,
    attempts INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    partial_count INT NOT NULL DEFAULT 0,
    wrong_count INT NOT NULL DEFAULT 0,
    duration_seconds INT NOT NULL DEFAULT 0,
    avg_response_ms INT NOT NULL DEFAULT 0,
    new_learned INT NOT NULL DEFAULT 0,
    review_learned INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_daily_user_date (user_id, learning_date),
    CONSTRAINT fk_daily_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- SM-2 调度历史快照
CREATE TABLE IF NOT EXISTS word_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    word_id VARCHAR(36) NOT NULL,
    repetitions INT NOT NULL DEFAULT 0,
    interval_days INT NOT NULL DEFAULT 0,
    ef FLOAT NOT NULL DEFAULT 2.5,
    next_review_at DATETIME NULL,
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_snap_user (user_id),
    KEY idx_snap_word (word_id),
    KEY idx_snap_captured (captured_at),
    CONSTRAINT fk_snap_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_snap_word FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 回滚: DROP TABLE word_snapshots, daily_stats, user_preferences;
--       ALTER TABLE learning_records DROP COLUMN is_new, DROP COLUMN response_ms;
-- ============================================
