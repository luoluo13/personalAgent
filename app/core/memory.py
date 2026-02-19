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
        
        cursor.execute(
            "INSERT INTO conversations (user_id, message, role) VALUES (?, ?, ?)",
            (user_id, message, role)
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error deleting SQLite data for {user_id}: {e}")
            raise e # Re-raise for SQLite as it is critical

memory_service = MemoryService()
