-- ============================================
-- 迁移脚本: 004_add_meta_data_to_words.sql
-- 描述: 给 words 表添加 meta_data 和 updated_at 字段
-- 作者: XuLin8
-- 日期: 2026-08-20
-- 版本: 004
-- 原因: 支持音标、词组配置等可扩展字段
-- ============================================

-- 执行迁移
ALTER TABLE words ADD COLUMN meta_data JSON DEFAULT NULL;
ALTER TABLE words ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- 为 JSON 字段中的常用查询创建虚拟列
ALTER TABLE words ADD COLUMN word_type VARCHAR(50) 
  GENERATED ALWAYS AS (JSON_UNQUOTE(JSON_EXTRACT(meta_data, '$.wordType'))) VIRTUAL;

ALTER TABLE words ADD COLUMN difficulty INT 
  GENERATED ALWAYS AS (JSON_EXTRACT(meta_data, '$.difficulty')) VIRTUAL;

-- 创建索引（提升查询速度）
CREATE INDEX idx_words_word_type ON words(word_type);
CREATE INDEX idx_words_difficulty ON words(difficulty);

-- 验证字段是否添加成功
-- SHOW COLUMNS FROM words;

-- ============================================
-- 回滚脚本
-- ALTER TABLE words DROP COLUMN meta_data;
-- ALTER TABLE words DROP COLUMN updated_at;
-- ALTER TABLE words DROP COLUMN word_type;
-- ALTER TABLE words DROP COLUMN difficulty;
-- ============================================