# test_openai.py 파일 생성해서 테스트
import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "안녕하세요!"}],
        max_tokens=50
    )
    print("✅ OpenAI API 연결 성공!")
    print("응답:", response.choices[0].message.content)
except Exception as e:
    print("❌ OpenAI API 오류:", e)