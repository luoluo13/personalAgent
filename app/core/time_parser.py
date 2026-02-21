from datetime import datetime
import json
import openai
from app.config import settings

class TimeParser:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )

    def parse_time_query(self, query: str) -> dict:
        """
        Parse natural language time query into date range.
        Returns a dict with 'start_date' and 'end_date' (YYYY-MM-DD string) or None if no time found.
        """
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        weekday = now.strftime("%A")
        
        system_prompt = f"""
You are a precise time entity extraction system.
Current Date: {current_date} ({weekday})

Your task is to extract the time range mentioned in the user's query relative to the Current Date.
If the user mentions a specific date or relative time (e.g. "yesterday", "last week", "January 30th", "two days ago"), calculate the precise start and end dates.

Return ONLY a JSON object with:
- "start_date": "YYYY-MM-DD"
- "end_date": "YYYY-MM-DD"

If no specific time range is mentioned, return: {{"start_date": null, "end_date": null}}.

Examples:
Current: 2026-02-16 (Monday)

Query: "Do you remember my birthday last week?"
Output: {{"start_date": "2026-02-09", "end_date": "2026-02-15"}}

Query: "What did we talk about in January?"
Output: {{"start_date": "2026-01-01", "end_date": "2026-01-31"}}

Query: "I remember we talked about this two days ago"
Output: {{"start_date": "2026-02-14", "end_date": "2026-02-14"}}

Query: "Hello there"
Output: {{"start_date": null, "end_date": null}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.1,
                response_format={"type": "json_object"} 
            )
            
            result = response.choices[0].message.content
            
            if not result:
                return None
                
            parsed = json.loads(result)
            
            if not parsed.get("start_date") or not parsed.get("end_date"):
                return None
                
            return parsed
            
        except Exception as e:
            # print(f"Time extraction error: {e}") 
            return None

time_parser = TimeParser()
