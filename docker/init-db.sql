-- ==================== 校园垃圾分类AI助手 - PostgreSQL 初始化脚本 ====================
-- Docker 容器首次启动时自动执行
-- 此脚本由 docker-compose.yml 中的 db 服务挂载

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 注意：表结构由应用代码 (app/db.py) 自动创建
-- 此处仅创建扩展和初始管理员账户

-- 初始管理员账户（密码: admin123，生产环境必须修改）
-- 密码哈希使用 bcrypt 生成，此处为占位值
INSERT INTO users (id, username, password_hash, nickname, role, status, created_at, updated_at)
VALUES (
    uuid_generate_v4(),
    'admin',
    '$2b$12$LJ3m4ys3Lg2RqwmMeYdXjuR8kYFqH5QZKnX6X7vN8w9a0b1c2d3e4f5g6h7i8j9k',
    '系统管理员',
    'admin',
    'active',
    EXTRACT(EPOCH FROM NOW()),
    EXTRACT(EPOCH FROM NOW())
) ON CONFLICT (username) DO NOTHING;
