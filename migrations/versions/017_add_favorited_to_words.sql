-- ============================================
-- 迁移脚本: 017_add_favorited_to_words.sql
-- 描述: words 表增加收藏时间 favorited_at（生词本）
-- ============================================

-- 幂等：列不存在才添加
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'words' AND COLUMN_NAME = 'favorited_at');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE words ADD COLUMN favorited_at DATETIME NULL COMMENT "收藏时间（非空=已收藏）"',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
