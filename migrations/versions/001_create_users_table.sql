-- ============================================
-- 迁移脚本: 001_create_users_table.sql
-- 描述: 创建 users 表
-- 作者: XuLin8
-- 日期: 2026-08-20
-- 版本: 001
-- ============================================

-- 执行迁移
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 回滚脚本 (执行: mysql -u root -p -e "DROP TABLE users;")
-- ============================================