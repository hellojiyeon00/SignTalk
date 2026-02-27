import os
import logging
from openai import OpenAI
from model_app.core.config import settings

# 로거 설정
logger = logging.getLogger("llm-service")
logging.basicConfig(level=logging.INFO)

# OpenAI 클라이언트 초기화
client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_URL
)

async def translate_gloss2text(gloss_list):
    """
    수어 글로스 시퀀스를 자연스러운 한국어 문장으로 변환
    """
    if not gloss_list:
        return ""

    # 글로스 리스트를 공백으로 구분된 문자열로 변환
    gloss_content = " ".join(gloss_list)
    
    try:
        logger.info(f"🤖 [LLM] 문장 변환 요청: {gloss_content}")

        """response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 수어 번역 전문가야. 입력되는 수어 글로스(단어)들을 보고 "
                        "한국어 문법에 맞는 자연스러운 문장으로 의역해줘. "
                        "결과물에 설명이나 따옴표 등 부가 정보는 일절 배제하고 '최종 문장'만 출력해."
                    )
                },
                {
                    "role": "user",
                    "content": gloss_content
                }
            ],
            temperature=0.3 # 일관된 답변을 위해 낮은 자유도 설정
        )

        final_text = response.choices[0].message.content.strip()"""
        final_text = "안녕하세요!"
        logger.info(f"✅ [LLM] 변환 완료: {final_text}")
        
        return final_text

    except Exception as e:
        logger.error(f"❌ [LLM] API 호출 중 오류 발생: {e}")
        # 오류 발생 시 단어들을 단순히 합친 결과라도 반환
        return " ".join(gloss_list)