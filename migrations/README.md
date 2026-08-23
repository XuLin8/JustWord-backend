# 数据库迁移说明

本目录包含 JustWord 后端项目的所有数据库迁移脚本，用于管理数据库结构的版本变更。

---

## 📁 目录结构

```text
migrations/
├── versions/                          # 迁移脚本存放目录
│   ├── 001_create_users_table.sql
│   ├── 002_create_words_table.sql
│   ├── 003_create_learning_records.sql
│   ├── 004_add_metadata_to_words.sql
│   └── 005_seed_default_words.sql
└── README.md                          # 本文件
```

---

# 📄 迁移脚本命名规范

格式：

```text
{版本号}_{描述}.sql
```

示例：

```text
001_create_users_table.sql
002_create_words_table.sql
003_create_learning_records.sql
004_add_metadata_to_words.sql
005_seed_default_words.sql
```

命名规则：

| 部分 | 说明 |
| --- | --- |
| 版本号 | 三位数字，从 `001` 开始递增 |
| 描述 | 使用小写英文，下划线分隔单词 |

---

# 🚀 使用方法

## 1. 首次部署（创建所有表）

进入项目根目录：

```bash
cd F:\Dev\JustWord-backend
```

---

### 方法一：逐个执行迁移

```bash
mysql -u root -p justword < migrations/versions/001_create_users_table.sql

mysql -u root -p justword < migrations/versions/002_create_words_table.sql

mysql -u root -p justword < migrations/versions/003_create_learning_records.sql

mysql -u root -p justword < migrations/versions/004_add_metadata_to_words.sql

mysql -u root -p justword < migrations/versions/005_seed_default_words.sql
```

---

### 方法二：一次执行所有迁移

Linux / macOS：

```bash
cat migrations/versions/*.sql | mysql -u root -p justword
```

Windows PowerShell：

```powershell
Get-Content migrations/versions/*.sql | mysql -u root -p justword
```

---

## 2. 新增迁移脚本

步骤：

1. 在 `versions/` 目录创建新文件：

例如：

```text
006_add_phonetic_field.sql
```

2. 编写 SQL 变更语句。

3. 执行迁移：

```bash
mysql -u root -p justword < migrations/versions/006_add_phonetic_field.sql
```

---

# 📄 迁移脚本模板

```sql
-- ============================================
-- 迁移脚本: {版本号}_{描述}.sql
-- 描述: {描述此迁移的作用}
-- 作者: {作者名}
-- 日期: {YYYY-MM-DD}
-- 版本: {版本号}
-- ============================================


-- 执行迁移
{SQL 变更语句，例如:
ALTER TABLE words ADD COLUMN phonetic VARCHAR(255);
}


-- 创建索引（如需要）
-- CREATE INDEX idx_xxx ON table_name(column_name);


-- ============================================
-- 回滚脚本（如需回滚，执行以下 SQL）
-- ============================================

-- 示例:
-- ALTER TABLE words DROP COLUMN phonetic;
```

---

# 🔄 回滚迁移

查看对应迁移文件末尾的：

```sql
-- 回滚脚本
```

部分，然后手动执行。

示例：

回滚：

```text
004_add_metadata_to_words.sql
```

执行：

```bash
mysql -u root -p justword -e "ALTER TABLE words DROP COLUMN metadata;"

mysql -u root -p justword -e "ALTER TABLE words DROP COLUMN updated_at;"
```

---

# 📋 版本历史

| 版本 | 迁移脚本 | 描述 | 日期 |
| --- | --- | --- | --- |
| 001 | `001_create_users_table.sql` | 创建用户表 | 2026-08-20 |
| 002 | `002_create_words_table.sql` | 创建单词表 | 2026-08-20 |
| 003 | `003_create_learning_records.sql` | 创建学习记录表 | 2026-08-20 |
| 004 | `004_add_metadata_to_words.sql` | 添加 metadata 和 updated_at 字段 | 2026-08-20 |
| 005 | `005_seed_default_words.sql` | 添加默认示例数据（可选） | 2026-08-20 |
| 006 | `006_add_user_id_to_learning_records.sql` | 学习记录增加 user_id | 2026-08-24 |
| 007 | `007_add_srs_fields_to_words.sql` | 单词增加 SM-2 间隔重复调度字段 | 2026-08-24 |
| 008 | `008_create_checkins_table.sql` | 每日打卡表（连续天数统计） | 2026-08-24 |

---

# 🛠️ 常用命令速查

| 操作 | 命令 |
| --- | --- |
| 查看当前数据库版本 | `mysql -u root -p -e "SELECT * FROM migrations;"` |
| 执行单个迁移 | `mysql -u root -p justword < migrations/versions/xxx.sql` |
| 执行所有迁移 | `cat migrations/versions/*.sql \| mysql -u root -p justword` |
| 备份数据库 | `mysqldump -u root -p justword > backup.sql` |
| 查看表结构 | `mysql -u root -p -e "DESCRIBE justword.words;"` |

---

# ⚠️ 注意事项

## 1. 生产环境迁移前必须备份数据库

```bash
mysqldump -u root -p justword > backup_$(date +%Y%m%d).sql
```

---

## 2. 迁移脚本应保持幂等性

推荐使用：

```sql
IF NOT EXISTS
IF EXISTS
```

例如：

```sql
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY
);
```

---

## 3. 新增字段时考虑默认值

避免已有数据在迁移过程中出现：

- 插入失败
- 数据不完整
- 默认值缺失

---

## 4. 大表操作需谨慎

以下操作可能影响性能：

- 添加索引
- 修改字段类型
- 大批量数据更新

建议：

- 低峰期执行
- 提前测试
- 做好备份

---

# 📖 相关文档

- 项目 README：

```text
../README.md
```

- 后端部署指南：

```text
../DEPLOY.md
```