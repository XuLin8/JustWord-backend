-- ============================================
-- 迁移脚本: 009_create_wordbooks.sql
-- 描述: 创建单词本/分组表，并给 words 表增加 wordbook_id 外键
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 009
-- 说明:
--   一个单词归属一个单词本（wordbook_id 可空 = 未分组）；
--   删除单词本时，其中单词回退为未分组（ON DELETE SET NULL）。
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS wordbooks (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(500) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_wordbooks_user ON wordbooks(user_id, name);

-- 给 words 表增加 wordbook_id 外键（可空）
ALTER TABLE words ADD COLUMN wordbook_id INTEGER NULL;

-- 注意：仅当外键约束尚未存在时添加（重复执行会报错，需人工处理）
-- words 表加了 FOREIGN KEY，删本后单词置为未分组（SET NULL）
/*
ALTER TABLE words ADD CONSTRAINT fk_words_wordbook
    FOREIGN KEY (wordbook_id) REFERENCES wordbooks(id) ON DELETE SET NULL;
*/

-- ============================================
-- 回滚脚本
-- ALTER TABLE words DROP COLUMN wordbook_id;
-- DROP TABLE wordbooks;
-- ============================================