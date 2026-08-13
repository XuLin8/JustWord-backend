from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
import os

from ..schemas import JudgeRequest, JudgeResponse

router = APIRouter()

# 初始化 OpenAI 客户端（支持 DeepSeek）
client = AsyncOpenAI(
    base_url=os.getenv("AI_BASE_URL", "https://api.deepseek.com"),
    api_key=os.getenv("AI_API_KEY"),
)

@router.post("/judge", response_model=JudgeResponse)
async def judge_translation(req: JudgeRequest):
    try:
        prompt = f"""
        你是一个英语学习助手。判断用户的翻译是否正确。
        
        模式：{"英译汉" if req.mode == "en2zh" else "汉译英"}
        单词：{req.word}
        用户答案：{req.user_answer}
        正确答案：{req.correct_answer}
        
        返回 JSON:
        {{
            "is_correct": boolean,
            "score": number (0-100),
            "feedback": "简短评语",
            "suggestion": "如果错误，给出建议（可选）",
            "similar_words": ["相关近义词（可选）"]
        }}
        """
        
        response = await client.chat.completions.create(
            model=os.getenv("AI_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "你是英语学习助手，只返回 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return JudgeResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 判断失败: {str(e)}")