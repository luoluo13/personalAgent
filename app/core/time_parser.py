from datetime import datetime, timedelta
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
        current_date = datetime.now().strftime("%Y-%m-%d")
        weekday = datetime.now().strftime("%A")
        
        system_prompt = f"""
You are a precise time entity extraction system.
Current Date: {current_date} ({weekday})

Your task is to extract the time range mentioned in the user's query relative to the Current Date.
Return ONLY a JSON object with "start_date" and "end_date" in "YYYY-MM-DD" format.
If no specific time range is mentioned, return a JSON object with null values: {{"start_date": null, "end_date": null}}.

Examples:
Query: "Do you remember my birthday last week?"
Output: {{"start_date": "2023-10-23", "end_date": "2023-10-29"}} (assuming current date is 2023-11-02)

Query: "What did we talk about in January?"
Output: {{"start_date": "2024-01-01", "end_date": "2024-01-31"}}

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
            # print(f"Time extraction raw result: {result}") # Debug

            if not result:
                return None
                
            parsed = json.loads(result)
            
            # Check for null values explicitly
            if not parsed.get("start_date") or not parsed.get("end_date"):
                return None
                
            return parsed
            
        except Exception as e:
            # print(f"Time extraction error: {e}") # Suppress noise for normal non-time queries
            return None

time_parser = TimeParser()
