"""数据库抽象层，支持SQLite和PostgreSQL双模式"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseBackend:
    """数据库后端抽象基类，子类分别实现SQLite和PostgreSQL"""

    def connect(self) -> None:
        """建立数据库连接"""
        raise NotImplementedError

    def close(self) -> None:
        """关闭数据库连接"""
        raise NotImplementedError

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """执行单条 SQL 语句"""
        raise NotImplementedError

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条记录，返回字典或 None"""
        raise NotImplementedError

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        """查询多条记录，返回字典列表"""
        raise NotImplementedError

    def commit(self) -> None:
        """提交事务"""
        raise NotImplementedError


class SQLiteDatabase(DatabaseBackend):
    """SQLite后端，开发环境默认用这个，零配置"""

    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None

    def connect(self) -> None:
        import sqlite3
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            logger.info("SQLite 数据库连接成功: %s", self.db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> Any:
        if self._conn is None:
            self.connect()
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        row = self.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        rows = self.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()


class PostgreSQLDatabase(DatabaseBackend):
    """PostgreSQL后端，生产环境用"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None

    def connect(self) -> None:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            logger.error("psycopg2 未安装，请运行: pip install psycopg2-binary")
            raise

        if self._conn is None:
            self._conn = psycopg2.connect(self.database_url)
            self._conn.autocommit = False
            logger.info("PostgreSQL 数据库连接成功")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> Any:
        if self._conn is None:
            self.connect()
        cursor = self._conn.cursor()
        # 将 SQLite 风格的 ? 占位符替换为 %s
        pg_sql = sql.replace("?", "%s")
        cursor.execute(pg_sql, params)
        return cursor

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        import psycopg2.extras
        if self._conn is None:
            self.connect()
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        pg_sql = sql.replace("?", "%s")
        cursor.execute(pg_sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        import psycopg2.extras
        if self._conn is None:
            self.connect()
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        pg_sql = sql.replace("?", "%s")
        cursor.execute(pg_sql, params)
        return [dict(r) for r in cursor.fetchall()]

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()


def create_database() -> DatabaseBackend:
    """根据环境变量创建对应的数据库后端"""
    database_url = os.getenv("DATABASE_URL", "")

    if database_url and database_url.startswith("postgresql"):
        logger.info("使用 PostgreSQL 数据库后端")
        return PostgreSQLDatabase(database_url)

    # SQLite 模式
    db_path = os.getenv("DATABASE_PATH", "data/app.db")
    logger.info("使用 SQLite 数据库后端: %s", db_path)
    return SQLiteDatabase(db_path)


# 全局数据库实例（延迟初始化，在startup事件中调用init_database）
_db: Optional[DatabaseBackend] = None


def get_db() -> DatabaseBackend:
    """获取全局数据库实例"""
    global _db
    if _db is None:
        _db = create_database()
        _db.connect()
    return _db


def init_database() -> DatabaseBackend:
    """初始化数据库：建表、迁移、索引、种子数据，一次性搞定"""
    global _db
    _db = create_database()
    _db.connect()

    # 建表
    _init_tables(_db)
    # 迁移（仅 SQLite）
    if isinstance(_db, SQLiteDatabase):
        _migrate_sqlite(_db)
    # 索引
    _add_indexes(_db)
    # 种子数据
    _seed_data(_db)

    return _db


def _init_tables(db: DatabaseBackend) -> None:
    """创建所有业务表（幂等操作）"""
    # 使用标准 SQL 兼容 SQLite 和 PostgreSQL
    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            points INTEGER DEFAULT 0,
            checkin_count INTEGER DEFAULT 0,
            quiz_correct INTEGER DEFAULT 0,
            quiz_total INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            role TEXT DEFAULT 'user',
            phone TEXT DEFAULT '',
            oauth_provider TEXT DEFAULT '',
            oauth_id TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL DEFAULT 0,
            last_login REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS disposal_points (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            address TEXT DEFAULT '',
            categories TEXT DEFAULT '[]',
            zone TEXT DEFAULT '',
            is_indoor INTEGER DEFAULT 0,
            open_hours TEXT DEFAULT '',
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS checkins (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            point_id TEXT,
            lat REAL DEFAULT 0,
            lng REAL DEFAULT 0,
            photo_hash TEXT DEFAULT '',
            category TEXT DEFAULT '',
            points_earned INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS quiz_questions (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            answer INTEGER NOT NULL,
            explanation TEXT DEFAULT '',
            category TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 1,
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS quiz_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            selected INTEGER NOT NULL,
            is_correct INTEGER NOT NULL,
            points_earned INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            cover_image TEXT DEFAULT '',
            location TEXT DEFAULT '',
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            max_participants INTEGER DEFAULT 0,
            current_participants INTEGER DEFAULT 0,
            organizer TEXT DEFAULT '',
            creator_id TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_at REAL NOT NULL,
            updated_at REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS activity_signups (
            id TEXT PRIMARY KEY,
            activity_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT DEFAULT 'signed_up',
            checked_at TEXT DEFAULT '',
            created_at REAL NOT NULL,
            UNIQUE(activity_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS sms_codes (
            phone TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            expire_time REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at REAL NOT NULL
        )""",
    ]

    for sql in tables:
        db.execute(sql)
    db.commit()
    logger.info("数据库表初始化完成")


def _migrate_sqlite(db: SQLiteDatabase) -> None:
    """SQLite 数据库迁移：检测并补充缺失字段（幂等操作）"""
    expected_columns = {
        "users": {
            "oauth_provider": "TEXT DEFAULT ''",
            "oauth_id": "TEXT DEFAULT ''",
            "updated_at": "REAL DEFAULT 0",
            "status": "TEXT DEFAULT 'active'",
            "role": "TEXT DEFAULT 'user'",
            "phone": "TEXT DEFAULT ''",
        },
        "activities": {
            "creator_id": "TEXT DEFAULT ''",
            "updated_at": "REAL DEFAULT 0",
            "cover_image": "TEXT DEFAULT ''",
        },
        "activity_signups": {
            "status": "TEXT DEFAULT 'signed_up'",
            "checked_at": "TEXT DEFAULT ''",
        },
        "disposal_points": {
            "open_hours": "TEXT DEFAULT ''",
        },
    }

    for table, columns in expected_columns.items():
        # SQLite 用 PRAGMA table_info 获取列信息
        rows = db.fetchall(f"PRAGMA table_info({table})")
        existing = {r["name"] for r in rows}
        for col_name, col_def in columns.items():
            if col_name not in existing:
                try:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    logger.info("数据库迁移: %s.%s 字段已添加", table, col_name)
                except Exception as e:
                    logger.warning("数据库迁移跳过 [%s.%s]: %s", table, col_name, e)

    db.commit()
    logger.info("数据库迁移检查完成")


def _add_indexes(db: DatabaseBackend) -> None:
    """创建高频查询字段的索引（幂等操作）"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_checkins_user_id ON checkins(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_quiz_records_user_id ON quiz_records(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_quiz_records_date ON quiz_records(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_disposal_points_zone ON disposal_points(zone)",
        "CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider, oauth_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_signups_user ON activity_signups(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(status)",
        "CREATE INDEX IF NOT EXISTS idx_sms_codes_expire ON sms_codes(expire_time)",
    ]
    for sql in indexes:
        try:
            db.execute(sql)
        except Exception as e:
            logger.warning("索引创建跳过: %s", e)
    db.commit()
    logger.info("数据库索引优化完成")


def _seed_data(db: DatabaseBackend) -> None:
    """插入种子数据（仅在表为空时执行）"""
    _seed_disposal_points(db)
    _seed_quiz_questions(db)
    _seed_activities(db)


def _seed_disposal_points(db: DatabaseBackend) -> None:
    """投放点种子数据"""
    row = db.fetchone("SELECT COUNT(*) as cnt FROM disposal_points")
    if row and row["cnt"] > 0:
        return

    points = [
        {"id": "dp001", "name": "社区回收站A", "lat": 46.5935, "lng": 125.1410, "address": "朝阳区社区回收站A", "categories": ["可回收物", "厨余垃圾", "其他垃圾"], "zone": "朝阳区", "is_indoor": 0},
        {"id": "dp002", "name": "市民服务中心投放点", "lat": 46.5960, "lng": 125.1445, "address": "中心区市民服务中心", "categories": ["可回收物", "其他垃圾", "有害垃圾"], "zone": "中心区", "is_indoor": 1},
        {"id": "dp003", "name": "商业广场投放点", "lat": 46.5975, "lng": 125.1455, "address": "浦东新区商业广场", "categories": ["可回收物", "其他垃圾"], "zone": "浦东新区", "is_indoor": 1},
        {"id": "dp004", "name": "居民小区南门投放点", "lat": 46.5920, "lng": 125.1400, "address": "朝阳区居民小区南门", "categories": ["可回收物", "厨余垃圾", "其他垃圾", "有害垃圾"], "zone": "朝阳区", "is_indoor": 0},
        {"id": "dp005", "name": "公园西门投放点", "lat": 46.5985, "lng": 125.1395, "address": "海淀区公园西门", "categories": ["可回收物", "其他垃圾"], "zone": "海淀区", "is_indoor": 0},
        {"id": "dp006", "name": "写字楼大堂投放点", "lat": 46.5970, "lng": 125.1470, "address": "浦东新区写字楼大堂", "categories": ["可回收物", "有害垃圾", "其他垃圾"], "zone": "浦东新区", "is_indoor": 1},
        {"id": "dp007", "name": "社区菜场投放点", "lat": 46.5925, "lng": 125.1460, "address": "徐汇区社区菜场", "categories": ["可回收物", "厨余垃圾", "其他垃圾"], "zone": "徐汇区", "is_indoor": 0},
        {"id": "dp008", "name": "政务中心投放点", "lat": 46.5955, "lng": 125.1480, "address": "中心区政务中心", "categories": ["可回收物", "其他垃圾", "有害垃圾"], "zone": "中心区", "is_indoor": 1},
        {"id": "dp009", "name": "居民小区北门投放点", "lat": 46.5910, "lng": 125.1430, "address": "朝阳区居民小区北门", "categories": ["可回收物", "厨余垃圾", "其他垃圾", "有害垃圾"], "zone": "朝阳区", "is_indoor": 0},
        {"id": "dp010", "name": "体育中心投放点", "lat": 46.5990, "lng": 125.1420, "address": "海淀区体育中心", "categories": ["可回收物", "其他垃圾"], "zone": "海淀区", "is_indoor": 0},
    ]

    now = time.time()
    for p in points:
        db.execute(
            "INSERT INTO disposal_points (id, name, lat, lng, address, categories, zone, is_indoor, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (p["id"], p["name"], p["lat"], p["lng"], p["address"],
             json.dumps(p["categories"], ensure_ascii=False), p["zone"], p["is_indoor"], now)
        )
    db.commit()
    logger.info("投放点种子数据已插入: %d 条", len(points))


def _seed_quiz_questions(db: DatabaseBackend) -> None:
    """问答题目种子数据"""
    row = db.fetchone("SELECT COUNT(*) as cnt FROM quiz_questions")
    if row and row["cnt"] > 0:
        return

    questions = [
        {"id": "q001", "question": "用过的纸巾属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 3, "explanation": "用过的纸巾已被污染，无法回收再利用，属于其他垃圾。", "category": "其他垃圾", "difficulty": 1},
        {"id": "q002", "question": "过期药品应该投入哪个垃圾桶？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 2, "explanation": "过期药品含有化学成分，可能污染环境，属于有害垃圾。", "category": "有害垃圾", "difficulty": 1},
        {"id": "q003", "question": "喝完的易拉罐属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 0, "explanation": "易拉罐是铝制品，可以回收再利用，属于可回收物。", "category": "可回收物", "difficulty": 1},
        {"id": "q004", "question": "剩菜剩饭属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 1, "explanation": "剩菜剩饭是易腐烂的有机废弃物，属于厨余垃圾。", "category": "厨余垃圾", "difficulty": 1},
        {"id": "q005", "question": "废旧电池属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 2, "explanation": "废旧电池含有汞、铅等重金属，属于有害垃圾。", "category": "有害垃圾", "difficulty": 1},
        {"id": "q006", "question": "奶茶杯（含残余）应该如何分类？", "options": ["直接投入可回收物", "倒掉液体后杯身投入可回收物", "投入厨余垃圾", "投入其他垃圾"], "answer": 1, "explanation": "奶茶杯需要先倒掉残余液体，清洗后杯身属于可回收物。", "category": "可回收物", "difficulty": 2},
        {"id": "q007", "question": "外卖餐盒（有剩饭）如何正确处理？", "options": ["整体投入厨余垃圾", "整体投入其他垃圾", "剩饭入厨余，清洗餐盒入可回收物", "整体投入可回收物"], "answer": 2, "explanation": "应将剩饭和餐盒分离：剩饭属于厨余垃圾，清洗后的餐盒属于可回收物。", "category": "可回收物", "difficulty": 2},
        {"id": "q008", "question": "破碎的灯管属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 2, "explanation": "灯管含有汞等有害物质，即使破碎也属于有害垃圾，需小心包裹后投放。", "category": "有害垃圾", "difficulty": 2},
        {"id": "q009", "question": "大骨头（猪腿骨）属于什么垃圾？", "options": ["厨余垃圾", "其他垃圾", "可回收物", "有害垃圾"], "answer": 1, "explanation": "大骨头质地坚硬，不易腐烂降解，属于其他垃圾而非厨余垃圾。", "category": "其他垃圾", "difficulty": 2},
        {"id": "q010", "question": "日常生活中最常见的分类错误是什么？", "options": ["将塑料瓶投入其他垃圾", "将用过的纸巾投入可回收物", "将电池投入其他垃圾", "以上都是常见错误"], "answer": 3, "explanation": "以上三种都是日常生活中常见的分类错误，需要特别注意。", "category": "综合", "difficulty": 2},
        {"id": "q011", "question": "快递纸箱应该如何处理？", "options": ["直接投入可回收物", "拆除胶带后折叠投入可回收物", "投入其他垃圾", "投入厨余垃圾"], "answer": 1, "explanation": "快递纸箱应先拆除胶带和面单，折叠后投入可回收物。", "category": "可回收物", "difficulty": 2},
        {"id": "q012", "question": "指甲油属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 2, "explanation": "指甲油含有有机溶剂等化学成分，属于有害垃圾。", "category": "有害垃圾", "difficulty": 3},
        {"id": "q013", "question": "湿纸巾属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 3, "explanation": "湿纸巾材质不易降解且被污染，属于其他垃圾。", "category": "其他垃圾", "difficulty": 2},
        {"id": "q014", "question": "茶叶渣属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 1, "explanation": "茶叶渣是易腐烂的有机物，属于厨余垃圾。", "category": "厨余垃圾", "difficulty": 1},
        {"id": "q015", "question": "旧衣服属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 0, "explanation": "旧衣服可以回收再利用，属于可回收物。也可捐赠给有需要的人。", "category": "可回收物", "difficulty": 1},
    ]

    now = time.time()
    for q in questions:
        db.execute(
            "INSERT INTO quiz_questions (id, question, options, answer, explanation, category, difficulty, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (q["id"], q["question"], json.dumps(q["options"], ensure_ascii=False), q["answer"],
             q["explanation"], q["category"], q["difficulty"], now)
        )
    db.commit()
    logger.info("问答题目种子数据已插入: %d 条", len(questions))


def _seed_activities(db: DatabaseBackend) -> None:
    """活动种子数据"""
    row = db.fetchone("SELECT COUNT(*) as cnt FROM activities")
    if row and row["cnt"] > 0:
        return

    now = time.time()
    activities = [
        {"id": "act001", "title": "社区环保周——垃圾分类挑战赛", "description": "为期一周的垃圾分类知识竞赛和实践活动，参与即可获得环保积分！每日完成分类打卡，积分排名前10名将获得精美环保礼品。", "location": "社区活动中心", "start_time": now + 86400, "end_time": now + 86400 * 7, "max_participants": 200, "organizer": "社区环保协会"},
        {"id": "act002", "title": "社区垃圾分类志愿者招募", "description": "招募垃圾分类引导志愿者，每天在社区投放点引导居民正确分类。服务满5小时可获得志愿服务证明。", "location": "各社区投放点", "start_time": now + 43200, "end_time": now + 86400 * 14, "max_participants": 50, "organizer": "社区环保志愿队"},
        {"id": "act003", "title": "旧物回收市集", "description": "将闲置物品带到市集交换或捐赠，减少浪费从身边做起。可回收物包括旧书、旧衣、电子产品等。", "location": "社区文化广场", "start_time": now + 172800, "end_time": now + 172800 + 28800, "max_participants": 300, "organizer": "绿色社区联盟"},
    ]

    for a in activities:
        db.execute(
            "INSERT INTO activities (id, title, description, location, start_time, end_time, max_participants, organizer, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (a["id"], a["title"], a["description"], a["location"], a["start_time"], a["end_time"],
             a["max_participants"], a["organizer"], "open", now)
        )
    db.commit()
    logger.info("活动种子数据已插入: %d 条", len(activities))
