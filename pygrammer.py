import json
import csv
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# 1. API 설정
# 키는 환경 변수 GEMINI_API_KEY로 주입합니다. (.env.example 참고)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise SystemExit("GEMINI_API_KEY 환경 변수를 설정해주세요. (.env.example 참고)")
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_company_names(batch_size=50):
    """IT 스타트업 느낌의 세련된 영문 기업 이름 후보군을 생성합니다."""
    
    prompt = f"""
    Generate {batch_size} unique, creative, and modern startup company names in English.
    The names should sound like real-world tech companies (e.g., Vercel, Anthropic, Datadog, Linear).
    
    Mix different styles:
    - Abstract/Modern (e.g., Nexa, Aether)
    - Industry-focused (e.g., FinBase, BioLogic)
    - Action-oriented (e.g., Swiftly, Cloudify)
    - Lab/Studio style (e.g., Pixel Labs, Quantum Studio)

    Return a JSON list of strings:
    ["CompanyName1", "CompanyName2", ...]
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.0 # 창의성을 위해 온도를 높임
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error during API call: {e}")
        return []

def save_to_csv(data, filename="resources/company_names.csv"):
    """생성된 이름을 CSV 파일로 저장합니다."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # 중복 제거를 위해 set 사용 후 리스트화
    unique_names = list(set(data))
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 파일이 비어있을 때만 헤더 추가
        if f.tell() == 0:
            writer.writerow(["company_name"])
            
        for name in unique_names:
            writer.writerow([name])

# --- 실행부 ---
if __name__ == "__main__":
    total_needed = 200
    batch_size = 50 
    current_count = 0

    print(f"--- {total_needed}개의 기업 이름 후보 생성 시작 ---")

    while current_count < total_needed:
        names = generate_company_names(batch_size)
        if names:
            save_to_csv(names)
            current_count += len(names)
            print(f"현재 진행도: {current_count}/{total_needed}...")
        else:
            print("재시도 중...")

    print(f"\n완료! 'resources/company_names.csv'에 {current_count}개의 이름이 저장되었습니다.")