import openai
from app.config import settings
from app.core.memory import memory_service

class LLMService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )

    def generate_response(self, user_id: str, message: str, context_flags: dict = None):
        """
        Generate a response using DeepSeek-V3 with RAG and Persona.
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

        # 2. Retrieve relevant memories (Long-term memory)
        memories = memory_service.retrieve_relevant_memories(user_id, message)
        memory_context = "\n".join([f"- {m}" for m in memories])
        
        # 3. Get recent conversation history (Short-term memory)
        # We fetch from Redis or DB. Here we can use the DB fetch for simplicity and robustness
        recent_history = memory_service.get_recent_history(user_id, limit=10)
        
        # 4. Construct System Prompt
        # Replace placeholder with configured name
        formatted_system_prompt = settings.system_prompt.replace("{name}", settings.bot_name)
        
        # Append extra context from flags
        if extra_system_context:
            formatted_system_prompt += "\n\n" + "\n".join(extra_system_context)

        system_prompt = f"""{formatted_system_prompt}

【相关记忆】
{memory_context if memory_context else "暂无相关记忆"}

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
                model="deepseek-chat", # Assuming standard model name for V3
                messages=messages,
                temperature=1.3, # High temperature for more personality
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM Error: {e}")
            return "哥哥，我现在有点头晕，想不起来了... (API Error)"

llm_service = LLMService()
