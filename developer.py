import random
import csv

class Developer():
    _next_developer_id = 1 # 개발자 ID를 위한 클래스 레벨 카운터
    all_developers = {} # 모든 개발자 객체를 태그로 접근하기 위한 전역 레지스트리

    def __init__(self, firstSave=None, reputation=0, company_tag=None): # company_tag 추가
        self.tag = f"D{Developer._next_developer_id:05d}" # D00001, D00002 형식으로 태그 생성
        Developer._next_developer_id += 1 # 다음 개발자를 위해 카운터 증가
        Developer.all_developers[self.tag] = self # 생성된 개발자를 전역 레지스트리에 저장

        self.firstGen = firstSave
        self.gender = random.randint(0,1)
        self.career = [] # 개발자의 경력을 저장할 배열
        if company_tag:
            self.career.append(company_tag) # 소속된 회사의 태그를 경력에 추가
        self.createDev(reputation)
    def _openCSVFile(self, path):
        with open(path, 'r') as f:
            reader = csv.reader(f)
            return [row[0] for row in reader]
    
    def createDev(self, reputation):
        self.createName()
        self.createStats(reputation)

        print(f"Tag: {self.tag}, Name: {self.first_name} {self.last_name}")
        print(f"education: {self.education}\n\n")

    def createName(self):
        name_csv_male = 'resources/fixed_male.csv'
        name_csv_female = 'resources/fixed_female.csv'
        name_csv_lastnames = 'resources/surnameFix.csv'

        if self.gender:
            first_names = self._openCSVFile(name_csv_male)
        else:
            first_names = self._openCSVFile(name_csv_female)
        lastnames = self._openCSVFile(name_csv_lastnames)

        self.first_name = random.choice(first_names)
        self.last_name = random.choice(lastnames)
    
    def createStats(self, reputation):
        #피로도는 0-100, 100에서 최대 피로. 사기는 0-100, 100에서 최대 사기.
        self.fatigue = 0
        self.morale = 100

        #정신병은 0-20, 높을수록 근처 인물들에 악영향 가능성 높아짐
        psychological_issue_values = list(range(21)) # 0부터 20까지의 값
        psychological_issue_weights = [21 - i for i in range(21)] # 0에 21, 1에 20, ..., 20에 1의 가중치
        self.psychological_issue = random.choices(psychological_issue_values, weights=psychological_issue_weights, k=1)[0]

        #교육 수준(비전공자, 학사, 석사, 박사)
        education_list = ["None", "BD", "MD", "PhD"]
        if self.firstGen:
            if reputation < 5000:
                education_weights = [30, 100, 5, 1]
            elif reputation < 10000:
                education_weights = [20, 100, 20, 5]
            else:
                education_weights = [10, 100, 30, 10]
        else:
            education_weights = [20, 60, 15, 5]
        self.education = random.choices(education_list, weights=education_weights, k=1)[0]

        #전문분야(FE, BE, Mobile, AI, Ops, UIUX)
        # 1. 학위별 체급 설정 (최소 스탯 및 가용 포인트)
        # min_val: 모든 분야에 깔리는 최소 점수
        # bonus_points: 추가로 배분할 점수
        # focus: 전공 분야에 몰릴 확률 가중치
        edu_settings = {
            "None": {"min_val": (0, 3),   "bonus": 25, "focus": 3.0},
            "BD":   {"min_val": (4, 8),   "bonus": 40, "focus": 6.0},
            "MD":   {"min_val": (8, 12),  "bonus": 60, "focus": 12.0},
            "PhD":  {"min_val": (12, 18), "bonus": 90, "focus": 25.0} 
        }
        
        setting = edu_settings[self.education]
        fields = ["FE", "BE", "Mobile", "AI", "Ops", "UIUX"]
        self.main_field = random.choice(fields)

        # 2. 기본 체급(Base Line) 생성
        self.stats = {}
        for f in fields:
            self.stats[f] = random.randint(setting["min_val"][0], setting["min_val"][1])

        # 3. 보너스 포인트 가중치 분배
        remaining_points = setting["bonus"]
        weights = [setting["focus"] if f == self.main_field else 1.0 for f in fields]

        while remaining_points > 0:
            target = random.choices(fields, weights=weights, k=1)[0]
            if self.stats[target] < 50:
                self.stats[target] += 1
                remaining_points -= 1
            
            # 모든 스탯이 20이면 강제 종료
            if all(s == 50 for s in self.stats.values()):
                break
        self.CA = sum(self.stats.values())

        # PA (Potential Ability) generation
        # PA는 CA와 최대 능력치인 300 사이에서 생성됩니다. (PA >= CA)
        # PA가 CA에 더 가깝게 생성될 확률이 높도록 편향을 적용하되, 극단적인 값들을 줄입니다.
        pa_lower_bound = self.CA
        pa_upper_bound = 300 # 최대 능력치

        # PA가 CA에 더 가깝게 생성되도록 편향 지수(bias exponent)를 설정합니다.
        # exponent > 1 이면 낮은 값(pa_lower_bound, 즉 CA)에 가까운 값으로 편향됩니다.
        # 1.5는 PA가 CA에 비교적 가깝게 분포되도록 하면서도,
        # PA가 CA에 너무 붙거나 300에 너무 붙는 극단적인 경우를 줄이는 값입니다.
        # 이 값을 조절하여 PA-CA 차이의 분포를 미세 조정할 수 있습니다.
        exponent = 10

        # 0과 1 사이의 난수를 생성하고 편향 지수를 적용합니다.
        biased_random_factor = random.random() ** exponent
        
        # 편향된 난수를 PA 범위에 맞춰 스케일링하고 정수로 변환합니다.
        self.PA = int(pa_lower_bound + biased_random_factor * (pa_upper_bound - pa_lower_bound))
        
        print(f"[{self.education}] {self.main_field} 전문")
        print(f"Stats: {self.stats} (CA: {self.CA}, PA: {self.PA})")

    def to_dict(self):
        """객체를 딕셔너리 형태로 변환하여 JSON 직렬화에 사용"""
        return {
            "tag": self.tag,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "gender": self.gender,
            "firstGen": self.firstGen,
            "education": self.education,
            "main_field": self.main_field,
            "stats": self.stats,
            "CA": self.CA,
            "PA": self.PA,
            "fatigue": self.fatigue,
            "morale": self.morale,
            "psychological_issue": self.psychological_issue,
            "career": self.career # 경력 정보 포함
        }

if __name__ == "__main__":
    gen = Developer(True, 10000)