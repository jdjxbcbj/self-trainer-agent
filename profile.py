# -*- coding: utf-8 -*-
"""
profile.py - 用户画像（长时记忆）

用标准库 sqlite3 把用户画像持久化到本地 SQLite 文件。
每个 user_id 对应一行，画像数据整体以 JSON 字符串存储。

为什么用 JSON 字符串而非分列存储：
用户画像的字段会随着产品迭代（复盘 Agent 产出不同的 profile_update）
动态变化，JSON 保持结构灵活，无需频繁 ALTER TABLE。
"""

import sqlite3
import json
import os

# 数据库文件与本模块放在同一目录，避免依赖当前工作目录
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.db")


class UserProfile:
    """用户画像存储，提供 get / update 两个接口"""

    def __init__(self):
        # 首次创建连接时自动建表（IF NOT EXISTS 保证幂等，重复初始化不报错）
        self._init_db()

    def _init_db(self):
        """
        初始化数据库连接并创建 profiles 表。

        为什么每次 __init__ 都建新连接：sqlite3 连接非线程安全，
        保持「每次操作都新建短连接」更稳妥，避免共享连接在多 Agent 并发下的隐患。
        """
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    data TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, user_id):
        """
        读取指定用户的画像。

        返回:
            dict: 该用户画像；不存在时返回空 dict {}。
        """
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.execute(
                "SELECT data FROM profiles WHERE user_id = ?", (user_id,)
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            print(f"[UserProfile] 未找到用户 {user_id} 的画像，返回空 dict")
            return {}

        data = json.loads(row[0])
        print(f"[UserProfile] 已读取用户 {user_id} 的画像：{data}")
        return data

    def update(self, user_id, update):
        """
        增量更新用户画像：读出现有画像，浅合并 update，再写回。

        参数:
            user_id: 用户ID
            update: 要合并进画像的增量 dict

        为什么浅合并（existing.update(update)）就够：
        当前画像的每个字段都是扁平标量（如 practice_count、weak_points 的
        汇总计数），复盘 Agent 产出的 profile_update 也是对顶层字段的整体覆盖，
        不存在「嵌套 dict 需递归合并」的场景。浅合并语义清晰、足够，且避免了
        递归合并带来的复杂性与误合并风险。
        """
        existing = self.get(user_id)

        # 浅合并：update 中出现的键覆盖现有同名字段，未出现的键保留原值
        existing.update(update)

        conn = sqlite3.connect(DB_PATH)
        try:
            # INSERT OR REPLACE：同一 user_id 已存在则整行替换，保证幂等更新
            conn.execute(
                "INSERT OR REPLACE INTO profiles (user_id, data) VALUES (?, ?)",
                (user_id, json.dumps(existing, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

        print(f"[UserProfile] 用户 {user_id} 画像已更新：{existing}")
