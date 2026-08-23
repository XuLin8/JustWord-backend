-- ============================================
-- 迁移脚本: 012_create_wrong_words.sql
-- 描述: 创建错题/薄弱词表
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 012
-- 说明:
--   复习答错时自动 upsert（一用户一词一条，累积 wrong_count）；
--   单词被删除时对应错题记录级联删除。
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS wrong_words (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(36) NOT NULL,
    word_id VARCHAR(36) NOT NULL,
    wrong_count INTEGER NOT NULL DEFAULT 1,
    last_wrong_at DATETIME,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_wrong_user_word (user_id, word_id),
    CONSTRAINT fk_wrong_words_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_wrong_words_word FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

-- 供按用户分页查询错题用
CREATE INDEX idx_wrong_words_user ON wrong_words(user_id, status);

-- ============================================
-- 回滚脚本
-- DROP TABLE wrong_words;
-- ============================================