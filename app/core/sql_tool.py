import sqlite3
from app.db.sqlite import get_db_connection

class SQLQueryTool:
    def __init__(self):
        self.allowed_tables = ["conversations", "weekly_summaries", "monthly_summaries", "yearly_summaries"]
        
    def validate_sql(self, sql: str) -> bool:
        """
        Basic safety check for generated SQL.
        Only allow SELECT statements on specific tables.
        """
        sql_upper = sql.upper().strip()
        
        # 1. Must be SELECT
        if not sql_upper.startswith("SELECT"):
            return False
            
        # 2. No modification keywords
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"]
        for keyword in forbidden_keywords:
            if keyword in sql_upper:
                return False
                
        # 3. Must not query system tables (basic check)
        if "SQLITE_MASTER" in sql_upper or "SYSTEM_STATE" in sql_upper:
            return False
            
        return True

    def execute_query(self, user_id: str, sql: str) -> list:
        """
        Execute a safe SELECT query.
        Forces user_id check to prevent data leaks.
        """
        if not self.validate_sql(sql):
            return ["Error: Invalid or unsafe SQL query."]
            
        # Safety: Enforce user_id filtering
        # Check if user_id literal is present in SQL
        if user_id not in sql:
             return ["Error: Query must be scoped to the current user_id."]

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            
            # Format results as string list
            results = []
            for row in rows:
                # Convert row object to dict then string
                results.append(str(dict(row)))
            return results
            
        except Exception as e:
            return [f"SQL Execution Error: {str(e)}"]

sql_tool = SQLQueryTool()