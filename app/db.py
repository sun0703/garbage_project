import sqlite3
import json
import time
import hashlib
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            logger.info("数据库连接成功: %s", self.db_path)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn

    def init_tables(self):
        c = self.conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
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
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS disposal_points (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                address TEXT DEFAULT '',
                categories TEXT DEFAULT '[]',
                campus_zone TEXT DEFAULT '',
                is_indoor INTEGER DEFAULT 0,
                open_hours TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                point_id TEXT,
                lat REAL DEFAULT 0,
                lng REAL DEFAULT 0,
                photo_hash TEXT DEFAULT '',
                category TEXT DEFAULT '',
                points_earned INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                answer INTEGER NOT NULL,
                explanation TEXT DEFAULT '',
                category TEXT DEFAULT '',
                difficulty INTEGER DEFAULT 1,
                created_at REAL NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS quiz_records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                selected INTEGER NOT NULL,
                is_correct INTEGER NOT NULL,
                points_earned INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS activities (
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
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS activity_signups (
                id TEXT PRIMARY KEY,
                activity_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT DEFAULT 'signed_up',
                checked_at TEXT DEFAULT '',
                created_at REAL NOT NULL,
                UNIQUE(activity_id, user_id),
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS sms_codes (
                phone TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                expire_time REAL NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        self.conn.commit()
        logger.info("数据库表初始化完成")

    def migrate(self):
        """数据库版本迁移——检测并补充旧数据库中缺失的字段（幂等操作）"""
        c = self.conn.cursor()

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
            c.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in c.fetchall()}
            for col_name, col_def in columns.items():
                if col_name not in existing:
                    try:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                        logger.info("数据库迁移: %s.%s 字段已添加", table, col_name)
                    except Exception as e:
                        logger.warning("数据库迁移跳过 [%s.%s]: %s", table, col_name, e)

        self.conn.commit()

        # 迁移旧 activities 表的 cover_url → cover_image 数据
        try:
            c.execute("PRAGMA table_info(activities)")
            act_cols = {row[1] for row in c.fetchall()}
            if "cover_url" in act_cols and "cover_image" in act_cols:
                c.execute("UPDATE activities SET cover_image = cover_url WHERE cover_image = '' AND cover_url != ''")
                self.conn.commit()
                logger.info("数据库迁移: activities.cover_url 数据已迁移到 cover_image")
        except Exception as e:
            logger.warning("数据库迁移跳过 [activities.cover_url→cover_image]: %s", e)

        logger.info("数据库迁移检查完成")

    def add_indexes(self):
        """创建高频查询字段的索引（幂等操作，重复执行安全）"""
        c = self.conn.cursor()
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_checkins_user_id ON checkins(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_quiz_records_user_id ON quiz_records(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_quiz_records_date ON quiz_records(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_disposal_points_campus ON disposal_points(campus_zone)",
            "CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider, oauth_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_signups_user ON activity_signups(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(status)",
            "CREATE INDEX IF NOT EXISTS idx_sms_codes_expire ON sms_codes(expire_time)",
        ]
        for sql in indexes:
            try:
                c.execute(sql)
            except Exception as e:
                logger.warning("索引创建跳过: %s", e)
        self.conn.commit()
        logger.info("数据库索引优化完成")

    def seed_disposal_points(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM disposal_points")
        if c.fetchone()[0] > 0:
            return

        points = [
            {"id": "dp001", "name": "一食堂南门投放点", "lat": 30.7585, "lng": 103.9345, "address": "一食堂南门出口右侧", "categories": ["可回收物", "厨余垃圾", "其他垃圾"], "campus_zone": "西区", "is_indoor": 0},
            {"id": "dp002", "name": "图书馆一楼大厅投放点", "lat": 30.7595, "lng": 103.9355, "address": "图书馆一楼大厅东侧", "categories": ["可回收物", "其他垃圾", "有害垃圾"], "campus_zone": "中心区", "is_indoor": 1},
            {"id": "dp003", "name": "教学楼A栋投放点", "lat": 30.7605, "lng": 103.9365, "address": "教学楼A栋一楼走廊", "categories": ["可回收物", "其他垃圾"], "campus_zone": "东区", "is_indoor": 1},
            {"id": "dp004", "name": "学生宿舍1号楼投放点", "lat": 30.7575, "lng": 103.9335, "address": "宿舍1号楼入口旁", "categories": ["可回收物", "厨余垃圾", "其他垃圾", "有害垃圾"], "campus_zone": "西区", "is_indoor": 0},
            {"id": "dp005", "name": "操场西侧投放点", "lat": 30.7610, "lng": 103.9320, "address": "操场西侧看台下方", "categories": ["可回收物", "其他垃圾"], "campus_zone": "西区", "is_indoor": 0},
            {"id": "dp006", "name": "实验楼投放点", "lat": 30.7600, "lng": 103.9380, "address": "实验楼B栋一楼", "categories": ["可回收物", "有害垃圾", "其他垃圾"], "campus_zone": "东区", "is_indoor": 1},
            {"id": "dp007", "name": "二食堂北门投放点", "lat": 30.7570, "lng": 103.9370, "address": "二食堂北门出口左侧", "categories": ["可回收物", "厨余垃圾", "其他垃圾"], "campus_zone": "东区", "is_indoor": 0},
            {"id": "dp008", "name": "行政楼投放点", "lat": 30.7590, "lng": 103.9390, "address": "行政楼一楼大厅", "categories": ["可回收物", "其他垃圾", "有害垃圾"], "campus_zone": "中心区", "is_indoor": 1},
            {"id": "dp009", "name": "学生宿舍5号楼投放点", "lat": 30.7565, "lng": 103.9350, "address": "宿舍5号楼入口旁", "categories": ["可回收物", "厨余垃圾", "其他垃圾", "有害垃圾"], "campus_zone": "西区", "is_indoor": 0},
            {"id": "dp010", "name": "体育馆投放点", "lat": 30.7615, "lng": 103.9340, "address": "体育馆入口处", "categories": ["可回收物", "其他垃圾"], "campus_zone": "西区", "is_indoor": 0},
        ]

        now = time.time()
        for p in points:
            c.execute(
                "INSERT INTO disposal_points (id, name, lat, lng, address, categories, campus_zone, is_indoor, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (p["id"], p["name"], p["lat"], p["lng"], p["address"],
                 json.dumps(p["categories"], ensure_ascii=False), p["campus_zone"], p["is_indoor"], now)
            )
        self.conn.commit()
        logger.info("投放点种子数据已插入: %d 条", len(points))

    def seed_quiz_questions(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM quiz_questions")
        if c.fetchone()[0] > 0:
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
            {"id": "q010", "question": "校园中最常见的分类错误是什么？", "options": ["将塑料瓶投入其他垃圾", "将用过的纸巾投入可回收物", "将电池投入其他垃圾", "以上都是常见错误"], "answer": 3, "explanation": "以上三种都是校园中常见的分类错误，需要特别注意。", "category": "综合", "difficulty": 2},
            {"id": "q011", "question": "快递纸箱应该如何处理？", "options": ["直接投入可回收物", "拆除胶带后折叠投入可回收物", "投入其他垃圾", "投入厨余垃圾"], "answer": 1, "explanation": "快递纸箱应先拆除胶带和面单，折叠后投入可回收物。", "category": "可回收物", "difficulty": 2},
            {"id": "q012", "question": "指甲油属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 2, "explanation": "指甲油含有有机溶剂等化学成分，属于有害垃圾。", "category": "有害垃圾", "difficulty": 3},
            {"id": "q013", "question": "湿纸巾属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 3, "explanation": "湿纸巾材质不易降解且被污染，属于其他垃圾。", "category": "其他垃圾", "difficulty": 2},
            {"id": "q014", "question": "茶叶渣属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 1, "explanation": "茶叶渣是易腐烂的有机物，属于厨余垃圾。", "category": "厨余垃圾", "difficulty": 1},
            {"id": "q015", "question": "旧衣服属于什么垃圾？", "options": ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"], "answer": 0, "explanation": "旧衣服可以回收再利用，属于可回收物。也可捐赠给有需要的人。", "category": "可回收物", "difficulty": 1},
        ]

        now = time.time()
        for q in questions:
            c.execute(
                "INSERT INTO quiz_questions (id, question, options, answer, explanation, category, difficulty, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (q["id"], q["question"], json.dumps(q["options"], ensure_ascii=False), q["answer"],
                 q["explanation"], q["category"], q["difficulty"], now)
            )
        self.conn.commit()
        logger.info("问答题目种子数据已插入: %d 条", len(questions))

    def seed_activities(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM activities")
        if c.fetchone()[0] > 0:
            return

        now = time.time()
        activities = [
            {"id": "act001", "title": "校园环保周——垃圾分类挑战赛", "description": "为期一周的垃圾分类知识竞赛和实践活动，参与即可获得环保积分！每日完成分类打卡，积分排名前10名将获得精美环保礼品。", "location": "图书馆报告厅", "start_time": now + 86400, "end_time": now + 86400 * 7, "max_participants": 200, "organizer": "校环保协会"},
            {"id": "act002", "title": "宿舍楼垃圾分类志愿者招募", "description": "招募垃圾分类引导志愿者，每天在宿舍楼投放点引导同学正确分类。服务满5小时可获得志愿服务证明。", "location": "各宿舍楼投放点", "start_time": now + 43200, "end_time": now + 86400 * 14, "max_participants": 50, "organizer": "学生会生活部"},
            {"id": "act003", "title": "旧物回收市集", "description": "将闲置物品带到市集交换或捐赠，减少浪费从身边做起。可回收物包括旧书、旧衣、电子产品等。", "location": "学生活动中心广场", "start_time": now + 172800, "end_time": now + 172800 + 28800, "max_participants": 300, "organizer": "绿色校园联盟"},
        ]

        for a in activities:
            c.execute(
                "INSERT INTO activities (id, title, description, location, start_time, end_time, max_participants, organizer, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (a["id"], a["title"], a["description"], a["location"], a["start_time"], a["end_time"],
                 a["max_participants"], a["organizer"], "open", now)
            )
        self.conn.commit()
        logger.info("活动种子数据已插入: %d 条", len(activities))


db = Database()
