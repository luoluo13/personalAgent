import openai
from app.config import settings
from app.core.memory import memory_service
from app.core.sql_tool import sql_tool

class LLMService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )

    def generate_response(self, user_id: str, message: str, context_flags: dict = None):
        """
        Generate a response using DeepSeek-V3 with RAG and Persona.
        Returns: (response_text, is_recalling)
        """
        # 1. Reload prompts to ensure latest configuration
        settings.reload_prompts()
        
        # Handle Context Flags
        extra_system_context = []
        if context_flags:
            if context_flags.get("interrupted_context"):
                extra_system_context.append(f"（注意：用户在上一轮对话中打断了你的发言，你当时说到：'{context_flags['interrupted_context']}'，请根据用户的新消息自然接续或转换话题）")
            if context_flags.get("network_error"):
                extra_system_context.append("（注意：用户刚刚遇到了网络错误，可能刚才的消息没发出去或重复了，请安抚用户）")
            if context_flags.get("memory_reset"):
                extra_system_context.append("（系统提示：用户刚刚重置了记忆库，你已经忘记了之前的所有对话，请重新认识用户）")
            if context_flags.get("chat_cleared"):
                extra_system_context.append("（系统提示：用户刚刚清空了聊天界面，这是新的一轮对话）")

        # 2. Intent Recognition & Smart Router
        intent_prompt = """
Analyze the user's message and determine the optimal retrieval strategy.
Return a JSON object with the following fields:

1. "intent_type": Choose one of:
   - "sql_query": Structured query about stats, time, count, first/last message (e.g. "when did we first meet?", "how many msgs yesterday?").
   - "vector_search": Semantic query about content/topics (e.g. "what did we say about X?", "that story about Y").
   - "hybrid_timeline": Query with both time range AND content (e.g. "what did we discuss last week about AI?").
   - "chat": Casual conversation, no retrieval needed.

2. "sql_statement": (Only if sql_query) Generate a valid SQLite SELECT statement.
   - Table: conversations
   - Columns: id, user_id, role ('user'/'assistant'), message, timestamp (YYYY-MM-DD HH:MM:SS)
   - ALWAYS filter by user_id = '{user_id}' (placeholder, will be replaced in code, or just rely on code injection) -> actually, generate standard SQL, code will handle safety.
   - Example: "SELECT timestamp FROM conversations WHERE role='user' ORDER BY id ASC LIMIT 1"

3. "search_keywords": (Only if vector_search/hybrid_timeline) List of specific entities, names, or terms for exact keyword matching (e.g. 'Project A', 'Alice').

4. "time_range_hint": (Only if hybrid_timeline) Boolean to trigger time parser.
"""
        # Inject current user_id into prompt context if needed for SQL generation guidance?
        # Better to let LLM generate generic SQL and we validate/bind user_id.
        # But for simplicity, let LLM generate valid SQL assuming it knows the schema.
        
        intent_check = self.complete(
            messages=[
                {"role": "system", "content": intent_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            json_mode=True
        )
        
        memories = []
        is_recalling = False
        is_time_query = False # Deprecated, merged into chat context via system prompt time
        
        if intent_check:
            import json
            try:
                intent_data = json.loads(intent_check)
                intent_type = intent_data.get("intent_type", "chat")
                
                if intent_type != "chat":
                    is_recalling = True
                    
                    # --- Route 1: SQL Engine ---
                    if intent_type == "sql_query":
                        # Handled in Post-processing block below to allow shared logic if needed
                        pass
                            
                    # --- Route 2: Hybrid Engine (Vector + Keyword) ---
                    elif intent_type == "vector_search":
                        keywords = intent_data.get("search_keywords", [])
                        # Call unified hybrid search
                        res = memory_service.retrieve_relevant_memories(
                            user_id, 
                            query=message,
                            keywords=keywords,
                            n_results=10
                        )
                        if isinstance(res, list): memories.extend(res)

                    # --- Route 3: Hybrid Engine ---
                    elif intent_type == "hybrid_timeline":
                        # 1. Parse time
                        time_range = time_parser.parse_time_query(message)
                        if time_range and time_range.get('start_date'):
                            # 2. Get raw logs from SQL
                            raw_logs = memory_service.get_memories_by_date_range(
                                user_id, 
                                time_range['start_date'], 
                                time_range['end_date'],
                                limit=100
                            )
                            # 3. Filter by keywords in Python
                            keywords = intent_data.get("search_keywords", [])
                            matched = []
                            for log in raw_logs:
                                if any(k.lower() in log.lower() for k in keywords):
                                    matched.append(log)
                            if not matched and len(raw_logs) < 20: matched = raw_logs
                            
                            if matched:
                                memories.append(f"【时间线混合检索 ({time_range['start_date']})】:\n" + "\n".join(matched[:20]))

                else:
                    is_recalling = False

                # Post-processing for SQL (Need user_id injection)
                if intent_type == "sql_query":
                    # We need to re-generate SQL with correct user_id if we want to be safe, 
                    # OR we just instruct LLM to use a placeholder and we replace it?
                    # Let's use placeholder '{user_id}' in prompt instruction.
                    raw_sql = intent_data.get("sql_statement", "")
                    if raw_sql:
                        # Replace placeholder if exists, or try to inject if missing (hard)
                        # Let's assume LLM follows instruction to filter by user_id.
                        # We will replace 'user_id_placeholder' if we asked for it.
                        # Let's just update the PROMPT above to say: "Use user_id = '{user_id}'"
                        # And here we format it.
                        final_sql = raw_sql.replace("{user_id}", user_id)
                        
                        # Execute
                        sql_results = sql_tool.execute_query(user_id, final_sql)
                        if sql_results:
                            memories.append(f"【结构化数据统计】:\n" + "\n".join(sql_results))

            except Exception as e:
                print(f"Intent processing error: {e}")
                pass 
        
        # Deduplicate and Format Memories
        unique_memories = list(set(memories))
        memory_context = "\n\n".join(unique_memories)
        
        # 3. Get recent conversation history (Short-term memory)
        recent_history = memory_service.get_recent_history(user_id, limit=10)
        
        # 4. Construct System Prompt
        from datetime import datetime
        
        now = datetime.now()
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        weekday_map = {0:"周一", 1:"周二", 2:"周三", 3:"周四", 4:"周五", 5:"周六", 6:"周日"}
        weekday_str = weekday_map[now.weekday()]
        
        # Calculate specific time info if requested
        # Even if is_time_query is false (deprecated), we always inject system time.
        # But for specific time questions, we might want to emphasize it.
        # Since we inject "Current System Time" at the top of prompt globally, 
        # the AI should be aware of time. 
        # Let's keep time_context simple or remove if redundant.
        # However, user feedback "lost time perception" suggests global prompt isn't enough?
        # Or maybe the "intent_type" logic bypassed some time handling?
        # Actually, in the new prompt, we removed "time_query" output field.
        # So is_time_query is always False.
        # And time_context block relies on it. 
        # FIX: Always inject detailed time context if it's a chat or time-related query?
        # Better yet, just make the global time header very explicit.
        
        # Enhanced Global Time Context
        formatted_system_prompt = settings.system_prompt.replace("{name}", settings.bot_name)
        
        # Explicitly formatted time block
        time_header = f"""
【系统时间广播】
当前现实时间：{current_time_str} ({weekday_str})
注意：请时刻感知此时间，如果用户问及时间，以此为准。
"""
        formatted_system_prompt = f"{time_header}\n\n{formatted_system_prompt}"
        
        if extra_system_context:
            formatted_system_prompt += "\n\n" + "\n".join(extra_system_context)

        system_prompt = f"""{formatted_system_prompt}

【相关记忆】
{memory_context if memory_context else "（本轮无需回忆）"}

请基于以上人设和记忆与用户对话。
"""

        # 5. Construct Messages
        messages = [{"role": "system", "content": system_prompt}]
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current user message
        messages.append({"role": "user", "content": message})

        # 6. Call LLM
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=1.3,
                stream=False
            )
            return response.choices[0].message.content, is_recalling
        except Exception as e:
            print(f"LLM Error: {e}")
            return "哥哥，我现在有点头晕，想不起来了... (API Error)", False

    def complete(self, messages: list, temperature: float = 0.7, json_mode: bool = False):
        """
        Generic completion method for internal tasks (summarization, extraction).
        """
        try:
            kwargs = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM Completion Error: {e}")
            return None

llm_service = LLMService()
