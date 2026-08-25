-- ============================================
-- 迁移脚本: 015_add_example_to_library_words.sql
-- 描述: library_words 增加例句(example)字段，用于四级词库音标/例句补齐
-- 作者: JustWord
-- 日期: 2026-08-25
-- 版本: 015
-- 说明:
--   1) example 存英文释义（ECDICT definition，完整英文句子）充当例句；
--   2) 数据回填由 migrations/backfill_cet4_ecdict.py 完成。
-- ============================================

-- 执行迁移：library_words 表增加例句列（可空）
ALTER TABLE library_words ADD COLUMN example VARCHAR(500) NULL COMMENT '例句，可空（ECDICT 英文释义）';

-- ============================================
-- 回滚脚本（如需回滚，执行以下 SQL）
-- ============================================
-- ALTER TABLE library_words DROP COLUMN example;
