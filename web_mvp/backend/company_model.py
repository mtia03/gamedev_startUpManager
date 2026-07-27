import random
import csv
from developer_model import Developer

class Corporate():
    _next_corporate_id = 1 # 회사 ID를 위한 클래스 레벨 카운터
    all_companies = {} # 모든 회사 객체를 태그로 접근하기 위한 전역 레지스트리

    def __init__(self, corporateClass):
        self.tag = f"C{Corporate._next_corporate_id:02d}" # C01, C02 형식으로 태그 생성
        Corporate._next_corporate_id += 1 # 다음 회사를 위해 카운터 증가
        Corporate.all_companies[self.tag] = self # 생성된 회사를 전역 레지스트리에 저장

        self.corporateClass = corporateClass
        self.staff_tags = [] # 회사에 소속된 개발자들의 태그를 저장할 리스트
        self.createName()
        self.createStats()

    def createName(self):
        companyCSV = 'resources/company_names.csv'
        with open(companyCSV, 'r') as f:
            reader = csv.reader(f)
            companyNames = [row[0] for row in reader]
        self.corporateName = random.choice(companyNames)
        print(f"Tag: {self.tag}, Name: {self.corporateName}")

    def createStats(self):
        minRep = [0, 5000, 10000]
        maxRep = [5000, 10000, 20000]
        self.reputation = random.randint(minRep[self.corporateClass], maxRep[self.corporateClass])
        
        maxStaffs = [30, 100, 300]
        self.staffNums = random.randint(maxStaffs[self.corporateClass]-20, maxStaffs[self.corporateClass])
        
        print(f"Tag: {self.tag}, Reputation: {self.reputation}, Staffs: {self.staffNums} staffs created:\n\n")

        for _ in range(self.staffNums):
            # 회사 태그를 개발자의 career에 추가하도록 Developer 생성자에 전달
            dev_instance = Developer(True, self.reputation, company_tag=self.tag)
            self.staff_tags.append(dev_instance.tag) # 생성된 개발자의 태그를 회사 staff_tags에 추가

    def to_dict(self):
        """객체를 딕셔너리 형태로 변환하여 JSON 직렬화에 사용"""
        return {
            "tag": self.tag,
            "corporateName": self.corporateName,
            "corporateClass": self.corporateClass,
            "reputation": self.reputation,
            "staffNums": self.staffNums,
            "staff_tags": self.staff_tags # 직원 태그 목록 포함
        }

# if __name__ == "__main__": # main.py에서 실행되므로 주석 처리 또는 제거
#     gen = Corporate(0)