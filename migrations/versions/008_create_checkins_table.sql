-- ============================================
-- 迁移脚本: 008_create_checkins_table.sql
-- 描述: 创建每日打卡表，用于连续天数统计
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 008
-- 说明:
--   user_id + date 唯一：一个用户每天只能打卡一次
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(36) NOT NULL,
    date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_checkin_user_date (user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 索引（按用户+日期查询）
CREATE INDEX idx_checkins_user_date ON checkins(user_id, date);

-- ============================================
-- 回滚脚本
-- DROP TABLE checkins;
-- ============================================