-- ============================================
-- 迁移脚本: 002_create_words_table.sql
-- 描述: 创建 words 表
-- 作者: XuLin8
-- 日期: 2026-08-20
-- 版本: 002
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS words (
    id VARCHAR(36) PRIMARY KEY,
    english VARCHAR(255) NOT NULL,
    chinese VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(36),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_words_english ON words(english);
CREATE INDEX idx_words_user_id ON words(user_id);

-- ============================================
-- 回滚脚本
-- DROP TABLE IF EXISTS words;
-- ============================================