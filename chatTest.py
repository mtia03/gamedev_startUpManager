import json
import os
from google import genai
from google.genai import types

# 1. 환경 설정 (API 키 입력)
# 키는 환경 변수 GEMINI_API_KEY로 주입합니다. (.env.example 참고)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)

def test_recruitment_processor(candidate_data, user_message, player_company_info, previous_message):
    # 응답 구조 정의 (Strict JSON)
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "dialogue": {"type": "STRING"},
            "past_conversation_summary": {"type": "STRING"}
        },
        "required": ["dialogue", "past_conversation_summary"]
    }

    system_instruction = """
    You are an AI agent acting as a software developer in a startup management game.
    Based on your current status and the user's recruitment proposal, decide whether to accept, negotiate, or reject.

    [TASK]
    0. Give out KOREAN dialogue. Use English only for the summary.
    1. Analyze message/company against 'disliked_people', 'morale', and 'fatigue'.
    2. Personality: Reflect 'psychopath_score' and 'origin' in tone. 
    3. Decision Logic: 
       - REJECT immediately if a 'disliked_person' is in the member list.
       - If 'morale' is low, more likely to NEGOTIATE or ACCEPT.
       - Be skeptical if 'company_reputation' is too low.
    4. Maintain a brief summary of the conversation history.
    5. NEVER mention exact numeric values of stats (e.g., "I have 20 stat").
    """

    # f-string 안에서 중괄호를 중복 사용하면 에러가 날 수 있으므로
    # 데이터는 미리 문자열로 변환해두는 것이 안전합니다.
    candidate_json = json.dumps(candidate_data, indent=4)
    company_json = json.dumps(player_company_info, indent=4)

    prompt = f"""
    You are an AI agent acting as a software developer in a startup management game.
    Based on your current status and the user's recruitment proposal, decide whether to accept, negotiate, or reject.

    [YOUR CURRENT STATUS (Hidden Data)]
    {candidate_json}

    [RECRUITER'S COMPANY INFO]
    {company_json}

    [PREVIOUS CONVERSATION]
    {previous_message}
    
    [USER'S MESSAGE]
    "{user_message}"
    
    [HOW TO UNDERSTAND STATS]
    - origin : bachelor, master, phd, or none.
        - tech_stack : the ability to perform task on certain roles. Max value is 20, and minimum value is 0.
        - morale : you may calculate it as percentage. the value of how much you can work properly, and give out your best result. Max value is 100 and minimum is 0. You can perform best on 100.
        - fatigue : you may calculate it as percentage. the value of how much you are tired from work. It may also mean how much you kind of hate your current company or position. Max value is 100 and minimum is 0, and you hate the most on 100.
        - psychopath_score : how much you may act selfish and give negative effect on your team. maximum score is 20, and you are most unsocializable on 20.
        - current_salary : how much you currently earn for working a year. Currency is USD.
        - disliked_people : list of people you hate for some specific reasons.
        - favorite_field : When you leave your current company for a new position, you may prefer to go for this field.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.7
            )
        )
        
        # 결과 출력
        if not response.text: return None
        result = json.loads(response.text)
        print("--- LLM Response ---")
        print(json.dumps(result, indent=4, ensure_ascii=False))
        return result["past_conversation_summary"]

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    target_dev = {
        "name": "James Miller",
        "origin": "Ph.D",
        "tech_stack": {"ML": 20, "DB": 5},
        "morale": 25,
        "fatigue": 70,
        "psychopath_score": 10,
        "current_salary": 5000,
        "disliked_people": [],
        "favorite_field": "ML"
    }

    my_startup = {
        "company_name": "Turbo Labs",
        "reputation": 45000,
        "members": ["John Doe", "Alice Smith"]
    }
    previous_message = ""
    while True:
        message = input("MSG: ")
        if message.lower() == "quit":
            break
        previous_message = test_recruitment_processor(target_dev, message, my_startup, previous_message)
        print("\n")