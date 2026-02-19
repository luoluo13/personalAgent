import json
from datetime import datetime, timedelta
import openai
from app.config import settings
from app.core.memory import memory_service
from app.db.sqlite import get_db_connection

class Summarizer:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )

    def _generate_llm_summary(self, context_text: str, level: str) -> dict:
        """
        Generate structured summary using LLM.
        level: 'week', 'month', 'year'
        """
        # Use deepseek-reasoner for higher-level abstractions (Month/Year)
        # Use deepseek-chat for basic summarization (Week)
        model_name = "deepseek-reasoner" if level in ["month", "year"] else "deepseek-chat"
        
        system_prompt = f"""
You are a professional memory architect. Your job is to distill conversation logs into high-level summaries.
Level: {level.upper()} SUMMARY

Input: Chronological conversation logs or lower-level summaries.
Output: A JSON object with the following fields:
- "summary": (string) A narrative summary of the period.
- "key_events": (list of objects) [{{"date": "YYYY-MM-DD", "event": "...", "importance": 0.1-1.0, "entities": ["tag1", "tag2"]}}]
- "emotional_trend": (string) E.g., "Happy -> Anxious -> Relieved"
- "relationship_milestone": (string or null) Any major change in relationship status.

Ensure "key_events" contains 3-5 most significant items.
Ensure "importance" is a float between 0.1 and 1.0.
"""
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context_text}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Summary generation error ({model_name}): {e}")
            return None

    def process_weekly_for_user(self, user_id: str):
        """Generate weekly summary for last week (L1)."""
        # ... (logic same as before) ...
        # Calculate last week's range
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        
        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = last_sunday.strftime("%Y-%m-%d")
        
        # 1. Get L0 Memories
        memories = memory_service.get_memories_by_range(user_id, start_date, end_date)
        if not memories:
            return 
            
        context_text = "\n".join([f"[{m['timestamp']}] {m['role']}: {m['message']}" for m in memories])
        
        # 2. Generate Summary (v3)
        result = self._generate_llm_summary(context_text, "week")
        if not result:
            return

        # 3. Save L1 Summary
        summary_id = memory_service.add_weekly_summary(
            user_id, 
            start_date, 
            result.get("summary", ""), 
            result.get("key_events", []), 
            result.get("emotional_trend", "")
        )
        
        # 4. Update Timeline (L1)
        for event in result.get("key_events", []):
            memory_service.add_timeline_entry(
                user_id=user_id,
                date_key=event.get("date", start_date),
                memory_id=f"summary_week_{summary_id}",
                layer=1,
                importance=event.get("importance", 0.5),
                entities=event.get("entities", []),
                content_preview=event.get("event", "")
            )
        
        print(f"Generated weekly summary for {user_id}")

    def process_monthly_for_user(self, user_id: str):
        """Generate monthly summary for last month (L2)."""
        today = datetime.now()
        # First day of current month
        first_day_curr_month = today.replace(day=1)
        # Last day of prev month
        last_day_prev_month = first_day_curr_month - timedelta(days=1)
        # First day of prev month
        first_day_prev_month = last_day_prev_month.replace(day=1)
        
        start_date = first_day_prev_month.strftime("%Y-%m-%d")
        end_date = last_day_prev_month.strftime("%Y-%m-%d")
        
        # 1. Get L1 Weekly Summaries for this month range
        weekly_summaries = memory_service.get_weekly_summaries_by_range(user_id, start_date, end_date)
        if not weekly_summaries:
            return # No weekly summaries to aggregate
            
        context_text = "\n".join([
            f"[Week {w['week_start']}] Summary: {w['summary']}\nEvents: {w['key_events']}\nMood: {w['emotional_trend']}" 
            for w in weekly_summaries
        ])
        
        # 2. Generate Summary (Reasoning Model)
        result = self._generate_llm_summary(context_text, "month")
        if not result:
            return
            
        # 3. Save L2 Summary
        summary_id = memory_service.add_monthly_summary(
            user_id,
            start_date,
            result.get("summary", ""),
            result.get("key_events", []),
            result.get("emotional_trend", ""),
            result.get("relationship_milestone", "")
        )
        
        # 4. Update Timeline (L2)
        for event in result.get("key_events", []):
            memory_service.add_timeline_entry(
                user_id=user_id,
                date_key=event.get("date", start_date),
                memory_id=f"summary_month_{summary_id}",
                layer=2,
                importance=event.get("importance", 0.7), # Higher base importance
                entities=event.get("entities", []),
                content_preview=event.get("event", "")
            )
        print(f"Generated monthly summary for {user_id}")

    def process_yearly_for_user(self, user_id: str):
        """Generate yearly summary for last year (L3)."""
        today = datetime.now()
        prev_year = today.year - 1
        start_date = f"{prev_year}-01-01"
        end_date = f"{prev_year}-12-31"
        
        # 1. Get L2 Monthly Summaries
        monthly_summaries = memory_service.get_monthly_summaries_by_range(user_id, start_date, end_date)
        if not monthly_summaries:
            return
            
        context_text = "\n".join([
            f"[Month {m['month_start']}] Summary: {m['summary']}\nEvents: {m['key_events']}\nMilestones: {m['relationship_milestone']}" 
            for m in monthly_summaries
        ])
        
        # 2. Generate Summary (Reasoning Model)
        result = self._generate_llm_summary(context_text, "year")
        if not result:
            return
            
        # 3. Save L3 Summary
        summary_id = memory_service.add_yearly_summary(
            user_id,
            start_date,
            result.get("summary", ""),
            result.get("key_events", []),
            result.get("emotional_trend", ""),
            result.get("relationship_milestone", "")
        )
        
        # 4. Update Timeline (L3)
        for event in result.get("key_events", []):
            memory_service.add_timeline_entry(
                user_id=user_id,
                date_key=event.get("date", start_date),
                memory_id=f"summary_year_{summary_id}",
                layer=3,
                importance=event.get("importance", 0.9), # Highest base importance
                entities=event.get("entities", []),
                content_preview=event.get("event", "")
            )
        print(f"Generated yearly summary for {user_id}")

    def run_all_weekly_summaries(self):
        """Entry point for scheduler (Weekly)."""
        self._run_for_all_users(self.process_weekly_for_user, "Weekly")

    def run_all_monthly_summaries(self):
        """Entry point for scheduler (Monthly)."""
        self._run_for_all_users(self.process_monthly_for_user, "Monthly")
        
    def run_all_yearly_summaries(self):
        """Entry point for scheduler (Yearly)."""
        self._run_for_all_users(self.process_yearly_for_user, "Yearly")

    def _run_for_all_users(self, process_func, task_name):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
        
        print(f"Starting {task_name} summary task for {len(users)} users...")
        for row in users:
            try:
                process_func(row["user_id"])
            except Exception as e:
                print(f"Error processing {task_name} for user {row['user_id']}: {e}")


summarizer = Summarizer()
