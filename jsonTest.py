import json
import os
import tkinter as tk
from tkinter import ttk, scrolledtext

def load_json_data(filename):
    """
    지정된 JSON 파일에서 데이터를 로드합니다.
    파일이 없으면 빈 리스트를 반환하고, 오류 발생 시 메시지를 출력합니다.
    """
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                print(f"Warning: '{filename}' does not contain a JSON list. Returning empty list.")
                return []
            return data
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{filename}': {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading '{filename}': {e}")
        return []

def show_developer_details_window(developer_info):
    """
    개발자의 상세 정보를 표시하는 새 창을 엽니다.
    """
    if not developer_info:
        return

    detail_window = tk.Toplevel()
    detail_window.title(f"개발자 상세 정보: {developer_info.get('first_name', '')} {developer_info.get('last_name', '')} ({developer_info.get('tag', '')})")
    detail_window.geometry("500x600")

    text_area = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD, width=60, height=30)
    text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    
    # 개발자 정보를 보기 좋게 리팩토링하여 출력
    content = []
    content.append(f"--- 기본 정보 ---")
    content.append(f"태그: {developer_info.get('tag', 'N/A')}")
    content.append(f"이름: {developer_info.get('first_name', 'N/A')} {developer_info.get('last_name', 'N/A')}")
    
    gender_map = {0: "여성", 1: "남성"}
    content.append(f"성별: {gender_map.get(developer_info.get('gender'), 'N/A')}")
    
    first_gen_map = {True: "초기 생성 개발자", False: "일반 개발자"}
    content.append(f"생성 유형: {first_gen_map.get(developer_info.get('firstGen'), 'N/A')}")
    
    content.append(f"학력: {developer_info.get('education', 'N/A')}")
    content.append(f"주요 분야: {developer_info.get('main_field', 'N/A')}")
    
    content.append("\n--- 능력치 ---")
    content.append(f"현재 능력치 (CA): {developer_info.get('CA', 'N/A')}")
    content.append(f"잠재 능력치 (PA): {developer_info.get('PA', 'N/A')}")
    
    stats = developer_info.get('stats', {})
    if stats:
        content.append("세부 스탯:")
        for field, value in stats.items():
            content.append(f"  - {field}: {value}")
    else:
        content.append("세부 스탯: N/A")

    content.append("\n--- 상태 ---")
    content.append(f"피로도: {developer_info.get('fatigue', 'N/A')}")
    content.append(f"사기: {developer_info.get('morale', 'N/A')}")
    content.append(f"정신 문제 지수: {developer_info.get('psychological_issue', 'N/A')}")

    content.append("\n--- 경력 ---")
    career = developer_info.get('career', [])
    content.append(f"소속 회사 태그: {', '.join(career) if career else '경력 없음'}")

    text_area.insert(tk.END, "\n".join(content))
    text_area.config(state=tk.DISABLED) # 텍스트 편집 불가

def show_company_staff_window(company_info, all_developers_dict):
    """
    특정 회사의 직원 목록을 표시하는 새 창을 엽니다.
    """
    if not company_info:
        return

    staff_window = tk.Toplevel()
    staff_window.title(f"{company_info.get('corporateName', '알 수 없는 회사')} 직원 목록")
    staff_window.geometry("400x500")

    tk.Label(staff_window, text=f"--- {company_info.get('corporateName', '회사')} 직원 ({len(company_info.get('staff_tags', []))}명) ---", font=("Helvetica", 14, "bold")).pack(pady=10)

    # 스크롤 가능한 프레임 생성 (속도 향상을 위해 간소화)
    staff_frame = ttk.Frame(staff_window)
    staff_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    # 스크롤바를 사용한 텍스트 위젯으로 변경 (성능 개선)
    canvas = tk.Canvas(staff_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(staff_frame, orient="vertical", command=canvas.yview)

    # 스크롤 가능한 컨텐츠 프레임
    scrollable_frame = tk.Frame(canvas)
    
    # 스크롤바와 캔버스 연결
    canvas.configure(yscrollcommand=scrollbar.set)

    # 캔버스에 프레임 연결
    canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    
    # 캔버스 크기 변경 시 프레임 너비 조정
    def on_canvas_configure(event):
        canvas.itemconfig(canvas_window_id, width=event.width)
    
    canvas.bind("<Configure>", on_canvas_configure)
    
    # 스크롤바와 캔버스를 프레임에 배치
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # 직원 목록 표시
    if not company_info.get('staff_tags'):
        tk.Label(scrollable_frame, text="직원이 없습니다.").pack(pady=5)
    else:
        for dev_tag in company_info['staff_tags']:
            developer_info = all_developers_dict.get(dev_tag)
            if developer_info:
                dev_button = ttk.Button(scrollable_frame, text=f"{developer_info.get('first_name', '')} {developer_info.get('last_name', '')} ({dev_tag})",
                                        command=lambda d=developer_info: show_developer_details_window(d))
                dev_button.pack(pady=2, fill=tk.X)
            else:
                tk.Label(scrollable_frame, text=f"알 수 없는 개발자: {dev_tag}").pack(pady=2)
    
    # 스크롤 영역 업데이트
    scrollable_frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Startup Manager Data Viewer")
    root.geometry("600x700")

    tk.Label(root, text="--- 회사 목록 ---", font=("Helvetica", 16, "bold")).pack(pady=20)

    # JSON 파일 로드 (속도 향상을 위해 최적화)
    corporate_data = load_json_data("corporate.json")
    developer_data = load_json_data("dev.json")

    # 개발자 데이터를 태그로 빠르게 찾을 수 있도록 딕셔너리로 변환 (O(1) 접근)
    all_developers_dict = {dev['tag']: dev for dev in developer_data}

    # 회사 클래스 매핑
    corporate_class_map = {
        0: "스타트업",
        1: "중견기업",
        2: "대기업"
    }

    # 회사 목록 프레임
    company_frame = ttk.Frame(root)
    company_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    # 빠른 버튼 생성 (기존 코드 유지)
    for company in corporate_data:
        company_class_str = corporate_class_map.get(company.get('corporateClass'), '알 수 없음')
        company_button = ttk.Button(company_frame, 
                                    text=f"{company.get('corporateName', '이름 없음')} ({company_class_str})",
                                    command=lambda c=company: show_company_staff_window(c, all_developers_dict))
        company_button.pack(pady=5, fill=tk.X)

    root.mainloop()