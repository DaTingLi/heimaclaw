"""
Token 使用统计模块

记录和分析 LLM token 使用情况。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from heimaclaw.console import info


class TokenUsageTracker:
    """
    Token 使用追踪器

    记录每次 LLM 调用的 token 使用情况。
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化 Token 追踪器

        参数:
            db_path: 数据库路径，默认 ~/.heimaclaw/data/tokens.db
        """
        self.db_path = db_path or Path.home() / ".heimaclaw" / "data" / "tokens.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建 token 使用记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                session_id TEXT,
                request_id TEXT,
                metadata TEXT
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_id
            ON token_usage(agent_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON token_usage(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_provider
            ON token_usage(provider)
        """)

        conn.commit()
        conn.close()

    def record(
        self,
        agent_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        记录 token 使用

        参数:
            agent_id: Agent ID
            provider: LLM 提供商
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            latency_ms: 延迟（毫秒）
            session_id: 会话 ID（可选）
            request_id: 请求 ID（可选）
            metadata: 其他元数据（可选）

        返回:
            记录 ID
        """
        total_tokens = prompt_tokens + completion_tokens
        timestamp = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO token_usage
            (timestamp, agent_id, provider, model, prompt_tokens,
             completion_tokens, total_tokens, latency_ms, session_id,
             request_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                agent_id,
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                session_id,
                request_id,
                json.dumps(metadata) if metadata else None,
            ),
        )

        record_id = cursor.lastrowid or 0
        conn.commit()
        conn.close()

        return record_id

    def get_stats(
        self,
        agent_id: Optional[str] = None,
        provider: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取 token 使用统计

        参数:
            agent_id: 过滤 Agent ID（可选）
            provider: 过滤提供商（可选）
            start_date: 开始日期（可选，YYYY-MM-DD）
            end_date: 结束日期（可选，YYYY-MM-DD）

        返回:
            统计数据字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)

        if provider:
            conditions.append("provider = ?")
            params.append(provider)

        if start_date:
            conditions.append("date(timestamp) >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("date(timestamp) <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查询统计
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as request_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(latency_ms) as avg_latency_ms,
                MIN(latency_ms) as min_latency_ms,
                MAX(latency_ms) as max_latency_ms
            FROM token_usage
            WHERE {where_clause}
        """,
            params,
        )

        row = cursor.fetchone()

        stats = {
            "request_count": row[0] or 0,
            "total_prompt_tokens": row[1] or 0,
            "total_completion_tokens": row[2] or 0,
            "total_tokens": row[3] or 0,
            "avg_latency_ms": round(row[4], 2) if row[4] else 0,
            "min_latency_ms": row[5] or 0,
            "max_latency_ms": row[6] or 0,
        }

        # 按提供商分组统计
        cursor.execute(
            f"""
            SELECT
                provider,
                COUNT(*) as count,
                SUM(total_tokens) as tokens
            FROM token_usage
            WHERE {where_clause}
            GROUP BY provider
            ORDER BY tokens DESC
        """,
            params,
        )

        stats["by_provider"] = [
            {"provider": row[0], "count": row[1], "tokens": row[2]}
            for row in cursor.fetchall()
        ]

        # 按模型分组统计
        cursor.execute(
            f"""
            SELECT
                model,
                COUNT(*) as count,
                SUM(total_tokens) as tokens
            FROM token_usage
            WHERE {where_clause}
            GROUP BY model
            ORDER BY tokens DESC
            LIMIT 10
        """,
            params,
        )

        stats["by_model"] = [
            {"model": row[0], "count": row[1], "tokens": row[2]}
            for row in cursor.fetchall()
        ]

        conn.close()

        return stats

    def get_daily_usage(
        self,
        agent_id: Optional[str] = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        获取每日使用量

        参数:
            agent_id: 过滤 Agent ID（可选）
            days: 查询最近多少天

        返回:
            每日使用量列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if agent_id:
            cursor.execute(
                """
                SELECT
                    date(timestamp) as date,
                    COUNT(*) as request_count,
                    SUM(total_tokens) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms
                FROM token_usage
                WHERE agent_id = ?
                  AND date(timestamp) >= date('now', '-' || ? || ' days')
                GROUP BY date(timestamp)
                ORDER BY date DESC
            """,
                (agent_id, days),
            )
        else:
            cursor.execute(
                """
                SELECT
                    date(timestamp) as date,
                    COUNT(*) as request_count,
                    SUM(total_tokens) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms
                FROM token_usage
                WHERE date(timestamp) >= date('now', '-' || ? || ' days')
                GROUP BY date(timestamp)
                ORDER BY date DESC
            """,
                (days,),
            )

        result = [
            {
                "date": row[0],
                "request_count": row[1],
                "total_tokens": row[2],
                "avg_latency_ms": round(row[3], 2) if row[3] else 0,
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return result

    def clear_old_records(self, days: int = 90) -> int:
        """
        清理旧记录

        参数:
            days: 保留最近多少天的数据

        返回:
            删除的记录数
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM token_usage
            WHERE date(timestamp) < date('now', '-' || ? || ' days')
        """,
            (days,),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        info(f"已清理 {deleted} 条旧记录（{days} 天前）")

        return deleted


# 全局追踪器
_global_tracker: Optional[TokenUsageTracker] = None


def get_token_tracker() -> TokenUsageTracker:
    """获取全局 Token 追踪器"""
    global _global_tracker

    if _global_tracker is None:
        _global_tracker = TokenUsageTracker()

    return _global_tracker


def record_token_usage(
    agent_id: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    **kwargs,
) -> int:
    """
    记录 token 使用（便捷函数）

    参数:
        agent_id: Agent ID
        provider: 提供商
        model: 模型
        prompt_tokens: 输入 token
        completion_tokens: 输出 token
        latency_ms: 延迟
        **kwargs: 其他参数

    返回:
        记录 ID
    """
    tracker = get_token_tracker()
    return tracker.record(
        agent_id=agent_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        **kwargs,
    )
