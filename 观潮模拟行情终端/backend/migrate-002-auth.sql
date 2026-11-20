-- 观潮后端迁移 002:登录限流 + 每用户 PBKDF2 迭代次数
-- 仅用于「已按旧版 schema.sql 建过库」的情况。全新部署直接执行 schema.sql 即可。
-- 执行: wrangler d1 execute guanchao --remote --file=./migrate-002-auth.sql
-- 注意:ALTER TABLE ADD COLUMN 只能执行一次,重复执行会报 duplicate column,可忽略。

ALTER TABLE users ADD COLUMN iterations INTEGER NOT NULL DEFAULT 30000;

CREATE TABLE IF NOT EXISTS login_attempts (
  key TEXT PRIMARY KEY,
  fails INTEGER NOT NULL,
  first_at INTEGER NOT NULL,
  locked_until INTEGER NOT NULL DEFAULT 0
);
