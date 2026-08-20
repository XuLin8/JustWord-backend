-- ============================================
-- 迁移脚本: 003_create_learning_records.sql
-- 描述: 创建 learning_records 表
-- 作者: XuLin8
-- 日期: 2026-08-20
-- 版本: 003
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS learning_records (
    id INTEGER NOT NULL AUTO_INCREMENT,
    word_id VARCHAR(36),
    mode VARCHAR(20),
    user_answer TEXT,
    correct_answer TEXT,
    result VARCHAR(20),
    score INTEGER,
    feedback TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_learning_records_word_id ON learning_records(word_id);
CREATE INDEX idx_learning_records_created_at ON learning_records(created_at);

-- ============================================
-- 回滚脚本
-- DROP TABLE IF EXISTS learning_records;
-- ============================================