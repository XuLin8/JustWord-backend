-- ============================================
-- 迁移脚本: 006_add_user_id_to_learning_records.sql
-- 描述: 给 learning_records 添加 user_id 字段（学习记录按用户隔离并持久化）
-- 作者: XuLin8
-- 日期: 2026-08-24
-- 版本: 006
-- ============================================

-- 执行迁移
ALTER TABLE learning_records ADD COLUMN user_id VARCHAR(36) NULL AFTER word_id;

-- 创建索引（按用户查询学习记录）
CREATE INDEX idx_learning_records_user_id ON learning_records(user_id);

-- 为已有记录按所属单词归属到单词 owner（可选，历史数据缺省）
-- UPDATE learning_records r
--   JOIN words w ON w.id = r.word_id
--   SET r.user_id = w.user_id
--   WHERE r.user_id IS NULL;

-- ============================================
-- 回滚脚本
-- ALTER TABLE learning_records DROP INDEX idx_learning_records_user_id;
-- ALTER TABLE learning_records DROP COLUMN user_id;
-- ============================================