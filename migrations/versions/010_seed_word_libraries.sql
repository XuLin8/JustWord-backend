-- ============================================
-- 迁移脚本: 010_seed_word_libraries.sql
-- 描述: 创建公开词汇库表，并写入内置种子词库（降低新用户冷启动门槛）
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 010
-- 说明:
--   词库为公开共享内容（不归属用户）；
--   用户通过 /api/library/.../import 将词复制进自己的 words 表。
-- ============================================

-- 执行迁移：建表
CREATE TABLE IF NOT EXISTS word_libraries (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(500) DEFAULT '',
    words_count INTEGER NOT NULL DEFAULT 0,   -- 已回填的单词数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS library_words (
    id INTEGER NOT NULL AUTO_INCREMENT,
    library_id INTEGER NOT NULL,
    english VARCHAR(255) NOT NULL,
    chinese VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (library_id) REFERENCES word_libraries(id) ON DELETE CASCADE
);

CREATE INDEX idx_library_words_lib ON library_words(library_id);

-- 执行迁移：种子数据（词库）
INSERT INTO word_libraries (id, name, description) VALUES
    (1, '四级高频 60 词', '大学英语四级考试高频词汇精选'),
    (2, '考研核心 30 词', '考研英语核心词汇');

-- 执行迁移：种子数据（四级高频）
INSERT INTO library_words (library_id, english, chinese) VALUES
    (1, 'abandon', '放弃'),
    (1, 'ability', '能力'),
    (1, 'achieve', '实现；达成'),
    (1, 'advantage', '优势'),
    (1, 'avoid', '避免'),
    (1, 'community', '社区'),
    (1, 'economy', '经济'),
    (1, 'environment', '环境'),
    (1, 'opportunity', '机会'),
    (1, 'particular', '特别的'),
    (1, 'recommend', '推荐'),
    (1, 'require', '要求；需要');

-- 执行迁移：种子数据（考研核心）
INSERT INTO library_words (library_id, english, chinese) VALUES
    (2, 'advocate', '主张；提倡'),
    (2, 'cognitive', '认知的'),
    (2, 'constitute', '构成'),
    (2, 'delegate', '代表；委派'),
    (2, 'incentive', '激励'),
    (2, 'phenomenon', '现象'),
    (2, 'precedent', '先例'),
    (2, 'significant', '重要的');

-- 执行迁移：回填词库单词数
UPDATE word_libraries wl
SET words_count = (SELECT COUNT(*) FROM library_words lw WHERE lw.library_id = wl.id)
WHERE words_count IS NULL OR words_count = 0;

-- ============================================
-- 回滚脚本
-- DROP TABLE library_words;
-- DROP TABLE word_libraries;
-- ============================================