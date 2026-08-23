-- ============================================
-- 迁移脚本: 011_expand_library1_to_full_cet4.sql
-- 描述: 将四级词库(id=1)从演示小样扩充为完整四级词表
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 011
-- 说明:
--   1) 侧重的四级数据存放在数据资产 migrations/data/cet4.tsv (4543 条)，
--      请使用加载脚本写入数据库，SQL 只负责建库级配置与清场:
--          python migrations/load_cet4.py [library_id]
--   2) 本脚本幂等：删除旧演示种、重命名库与描述。
-- ============================================

-- 执行迁移：清空旧演示种子（原 12 词为完整表的子集，按需删除避免重复）
DELETE FROM library_words WHERE library_id = 1;

-- 执行迁移：重命名并更新描述
UPDATE word_libraries
SET name = '大学英语四级完整词表',
    description = '大学英语四级完整词表（4543 词，数据源 KyleBing/english-vocabulary）'
WHERE id = 1;

-- 说明：批量词条数据由 migrations/load_cet4.py 读取 cet4.tsv 写入；
--       运行后回填 words_count。

-- ============================================
-- 回滚脚本（恢复演示种）
-- UPDATE word_libraries SET name='四级高频 60 词', description='大学英语四级考试高频词汇精选' WHERE id=1;
-- 删除后重新插入 12 词演示种即可。
-- ============================================