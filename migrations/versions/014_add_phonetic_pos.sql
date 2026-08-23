-- ============================================
-- 迁移脚本: 014_add_phonetic_pos.sql
-- 描述: words / library_words 增加音标(phonetic)与词性(part_of_speech)字段
-- ============================================

-- words 表
ALTER TABLE words ADD COLUMN phonetic VARCHAR(64) NULL COMMENT '音标，可空';
ALTER TABLE words ADD COLUMN part_of_speech VARCHAR(32) NULL COMMENT '词性缩写，如 v./n./adj.';

-- library_words 表
ALTER TABLE library_words ADD COLUMN phonetic VARCHAR(64) NULL COMMENT '音标，可空';
ALTER TABLE library_words ADD COLUMN part_of_speech VARCHAR(32) NULL COMMENT '词性缩写，如 v./n./adj.';