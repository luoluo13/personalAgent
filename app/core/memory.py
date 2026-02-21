import chromadb
from chromadb.config import Settings
from app.config import settings
from app.db.sqlite import get_db_connection
from app.db.redis_client import redis_client
import json
import time

class MemoryService:
    def __init__(self):
        # Initialize ChromaDB persistent client
        self.chroma_client = chromadb.PersistentClient(path=str(settings.chroma_path))
        
    def get_user_collection(self, user_id: str):
        """Get or create a Chroma collection for a specific user."""
        collection_name = f"memories_{user_id}"
        return self.chroma_client.get_or_create_collection(name=collection_name)

    def add_memory(self, user_id: str, content: str, metadata: dict = None):
        """Add a memory fragment to the vector database."""
        collection = self.get_user_collection(user_id)
        collection.add(
            documents=[content],
            metadatas=[metadata or {"timestamp": time.time()}],
            ids=[f"{user_id}_{time.time()}"]
        )

    def retrieve_relevant_memories(self, user_id: str, query: str, n_results: int = 5):
        """Retrieve relevant memories from vector database."""
        collection = self.get_user_collection(user_id)
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        if results['documents']:
            return results['documents'][0]
        return []

    def save_conversation(self, user_id: str, role: str, message: str):
        """Save conversation to SQLite and update Redis session."""
        # Save to SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure user exists
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        
        # Insert with explicit LOCAL timestamp from Python to ensure consistency
        # This overrides SQLite's default, making it independent of DB timezone settings
        from datetime import datetime
        now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO conversations (user_id, message, role, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, message, role, now_local)
        )
        conn.commit()
        conn.close()
        
        # Update Redis
        self._update_redis_session(user_id, role, message)

    def _update_redis_session(self, user_id: str, role: str, message: str):
        """Update session context and last active time in Redis."""
        key_active = f"chat:{user_id}:last_active"
        key_context = f"chat:{user_id}:session_context"
        
        # Update last active time
        redis_client.set(key_active, int(time.time()))
        
        # Update session context (keep last 10 messages for short-term memory)
        context = redis_client.lrange(key_context, 0, -1)
        if not context:
            context = []
        
        new_entry = json.dumps({"role": role, "content": message})
        redis_client.rpush(key_context, new_entry)
        
        # Trim to keep only last 20 messages
        if redis_client.llen(key_context) > 20:
            redis_client.lpop(key_context)

    def get_recent_history(self, user_id: str, limit: int = 20):
        """Get recent conversation history from SQLite."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, message as content, timestamp FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows][::-1]  # Reverse to chronological order

    # --- Phase 2: Hierarchical Memory & Hybrid Retrieval ---

    def add_timeline_entry(self, user_id: str, date_key: str, memory_id: str, layer: int, importance: float, entities: list, content_preview: str = None):
        """Add entry to memory timeline index."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_timeline 
            (user_id, date_key, memory_id, layer, importance, entities, content_preview) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, date_key, memory_id, layer, importance, json.dumps(entities), content_preview)
        )
        conn.commit()
        conn.close()

    def get_weekly_summaries_by_range(self, user_id: str, start_date: str, end_date: str):
        """Get L1 weekly summaries within a date range."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT summary, key_events, emotional_trend, week_start FROM weekly_summaries 
            WHERE user_id = ? AND week_start BETWEEN ? AND ?
            ORDER BY week_start ASC
            """,
            (user_id, start_date, end_date)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_monthly_summaries_by_range(self, user_id: str, start_date: str, end_date: str):
        """Get L2 monthly summaries within a date range."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT summary, key_events, emotional_trend, relationship_milestone, month_start FROM monthly_summaries 
            WHERE user_id = ? AND month_start BETWEEN ? AND ?
            ORDER BY month_start ASC
            """,
            (user_id, start_date, end_date)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_weekly_summary(self, user_id: str, week_start: str, summary: str, key_events: list, emotional_trend: str):
        """Add L1 weekly summary."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO weekly_summaries (user_id, week_start, summary, key_events, emotional_trend)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, week_start, summary, json.dumps(key_events), emotional_trend)
        )
        summary_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def add_monthly_summary(self, user_id: str, month_start: str, summary: str, key_events: list, emotional_trend: str, relationship_milestone: str):
        """Add L2 monthly summary."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO monthly_summaries (user_id, month_start, summary, key_events, emotional_trend, relationship_milestone)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, month_start, summary, json.dumps(key_events), emotional_trend, relationship_milestone)
        )
        summary_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def add_yearly_summary(self, user_id: str, year_start: str, summary: str, key_events: list, emotional_trend: str, relationship_milestone: str):
        """Add L3 yearly summary."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO yearly_summaries (user_id, year_start, summary, key_events, emotional_trend, relationship_milestone)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, year_start, summary, json.dumps(key_events), emotional_trend, relationship_milestone)
        )
        summary_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def get_memories_by_date_range(self, user_id: str, start_date: str, end_date: str, limit: int = 50, format_result: bool = True):
        """
        Retrieve raw conversation history within a specific date range from SQLite.
        
        Args:
            user_id: User ID
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD"
            limit: Max records
            format_result: If True, returns formatted strings. If False, returns dict list.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure range covers full days
        start_ts = f"{start_date} 00:00:00"
        end_ts = f"{end_date} 23:59:59"
        
        cursor.execute(
            """
            SELECT role, message, timestamp 
            FROM conversations 
            WHERE user_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (user_id, start_ts, end_ts, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        if not format_result:
            # Return raw dicts for summarizer
            return [dict(row) for row in rows]
            
        memories = []
        for row in rows:
            # Format: [2026-02-16 10:00] User: Hello
            ts = row['timestamp']
            role = row['role']
            content = row['message']
            memories.append(f"[{ts}] {role}: {content}")
            
        return memories

    def search_by_keyword(self, user_id: str, keywords: list, limit: int = 5):
        """
        Retrieve memories using keyword matching (SQLite LIKE).
        Returns list of strings.
        """
        if not keywords:
            return []
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic query for multiple keywords (OR logic)
        # We want to find messages containing ANY of the keywords
        conditions = []
        params = [user_id]
        
        for kw in keywords:
            conditions.append("message LIKE ?")
            params.append(f"%{kw}%")
            
        where_clause = " OR ".join(conditions)
        
        query = f"""
            SELECT role, message, timestamp 
            FROM conversations 
            WHERE user_id = ? AND ({where_clause})
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append(f"[{row['timestamp']}] {row['role']}: {row['message']}")
            
        return results

    def retrieve_relevant_memories(self, user_id: str, query: str, keywords: list = None, n_results: int = 5):
        """
        Retrieve relevant memories using Hybrid Search (Vector + Keyword) with RRF Fusion.
        """
        # 1. Vector Search (Semantic)
        collection = self.get_user_collection(user_id)
        vector_docs = []
        try:
            vector_results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            if vector_results['documents']:
                vector_docs = vector_results['documents'][0]
        except Exception as e:
            print(f"Vector search error: {e}")

        # 2. Keyword Search (Exact)
        keyword_docs = []
        if keywords:
            keyword_docs = self.search_by_keyword(user_id, keywords, limit=n_results)

        # 3. RRF Fusion (Reciprocal Rank Fusion)
        # Score = 1 / (k + rank)
        k = 60
        scores = {}
        
        # Process Vector Results
        for rank, doc in enumerate(vector_docs):
            # Clean up potential existing prefixes if any (though raw docs shouldn't have them)
            content = doc
            if content not in scores:
                scores[content] = 0
            scores[content] += 1 / (k + rank + 1)
            
        # Process Keyword Results
        for rank, doc in enumerate(keyword_docs):
            content = doc
            if content not in scores:
                scores[content] = 0
            scores[content] += 1 / (k + rank + 1)
            
        # Sort by score descending
        sorted_memories = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Top N
        final_memories = [item[0] for item in sorted_memories[:n_results]]
        
        # Add source prefix based on where it was found (optional, but helpful for debugging/LLM)
        # Actually, let's just mark them as [相关记忆] to be generic, or keep [语义联想] style?
        # The user wants "Precision". Let's just return the content. The LLM will see the content.
        # But to be consistent with previous logic, let's add a prefix if it's from vector?
        # No, let's keep it clean. The timestamp in keyword search result is already there.
        # Vector search result might not have timestamp in content (it stores raw text).
        # We should probably format vector results too if possible, but metadata is separate.
        # For now, let's just return the strings.
        
        return final_memories

    def delete_user_memory(self, user_id: str):
        """Delete all memories for a specific user from Chroma, Redis, and SQLite."""
        # 1. Delete from ChromaDB
        try:
            self.chroma_client.delete_collection(name=f"memories_{user_id}")
        except Exception as e:
            print(f"Error deleting Chroma collection for {user_id}: {e}")
            # Collection might not exist or other error, continue to delete other data

        # 2. Delete from Redis
        try:
            keys = redis_client.keys(f"chat:{user_id}:*")
            if keys:
                redis_client.delete(*keys)
        except Exception as e:
            print(f"Error deleting Redis keys for {user_id}: {e}")
            # Redis might be down, continue to delete SQLite data

        # 3. Delete from SQLite
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            # Phase 2: Delete summaries and timeline
            cursor.execute("DELETE FROM weekly_summaries WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM monthly_summaries WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM yearly_summaries WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM memory_timeline WHERE user_id = ?", (user_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error deleting SQLite data for {user_id}: {e}")
            raise e # Re-raise for SQLite as it is critical

memory_service = MemoryService()
