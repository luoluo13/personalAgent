import openai
from app.config import settings
from app.core.memory import memory_service
from app.core.time_parser import time_parser

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

        # 2. Extract Time Entity & Retrieve Memories (Conditional)
        # Use LLM to check intent for memory retrieval OR time calculation
        # Expanded Intent Prompt
        intent_prompt = """
Analyze the user's message and determine two things:
1. "need_retrieval": Does it require retrieving past memories/context? (e.g. "what did we talk about?", "my birthday")
2. "time_query": Is the user asking about current time, date, season, or time difference? (e.g. "what time is it?", "is it weekend?", "how long since last chat?")

Return JSON: {"need_retrieval": true/false, "time_query": true/false}
"""
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
        is_time_query = False
        
        if intent_check:
            import json
            try:
                intent_data = json.loads(intent_check)
                if intent_data.get("need_retrieval"):
                    is_recalling = True
                    time_range = time_parser.parse_time_query(message)
                    memories = memory_service.retrieve_relevant_memories(user_id, message, time_range=time_range)
                
                if intent_data.get("time_query"):
                    is_time_query = True
            except:
                pass # Fallback to defaults
        
        memory_context = "\n".join([f"- {m}" for m in memories])
        
        # 3. Get recent conversation history (Short-term memory)
        recent_history = memory_service.get_recent_history(user_id, limit=10)
        
        # 4. Construct System Prompt
        from datetime import datetime
        import locale
        # locale.setlocale(locale.LC_TIME, 'zh_CN.UTF-8') # Might not work on all Windows envs
        
        now = datetime.now()
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        weekday_map = {0:"周一", 1:"周二", 2:"周三", 3:"周四", 4:"周五", 5:"周六", 6:"周日"}
        weekday_str = weekday_map[now.weekday()]
        
        # Calculate specific time info if requested
        time_context = ""
        if is_time_query:
            # Add more detailed time info
            # E.g. Lunar date, Solar term (requires external lib, skip for now)
            # Just ensure detailed current time is emphasized
            time_context = f"【系统时间提示】当前精确时间：{current_time_str} {weekday_str}。请根据此时间准确回答用户的时间询问。"
        
        formatted_system_prompt = settings.system_prompt.replace("{name}", settings.bot_name)
        
        # Inject Current Time Context (Global)
        formatted_system_prompt = f"Current System Time: {current_time_str} {weekday_str}\n\n{formatted_system_prompt}"
        
        if extra_system_context:
            formatted_system_prompt += "\n\n" + "\n".join(extra_system_context)

        system_prompt = f"""{formatted_system_prompt}

{time_context}

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
