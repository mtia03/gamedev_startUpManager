import random
import csv
from developer_model import Developer, IdSequence

# 스크립트에서 Corporate()를 단독으로 만들 때만 쓰는 대체 발급기.
_standalone_ids = IdSequence("C", width=2)


class Corporate():
    def __init__(self, corporateClass, *, tag=None, rng=None, dev_ids=None):
        # 난수원과 태그 발급기를 주입받으면 전역 상태 없이 재현할 수 있다
        self.rng = rng or random
        self.dev_ids = dev_ids
        self.tag = tag or _standalone_ids.next()

        self.corporateClass = corporateClass
        self.staff_tags = [] # 회사에 소속된 개발자들의 태그를 저장할 리스트
        self.createName()
        self.createStats()

    def createName(self):
        companyCSV = 'resources/company_names.csv'
        with open(companyCSV, 'r') as f:
            reader = csv.reader(f)
            companyNames = [row[0] for row in reader]
        self.corporateName = self.rng.choice(companyNames)
        print(f"Tag: {self.tag}, Name: {self.corporateName}")

    def createStats(self):
        minRep = [0, 5000, 10000]
        maxRep = [5000, 10000, 20000]
        self.reputation = self.rng.randint(minRep[self.corporateClass], maxRep[self.corporateClass])

        maxStaffs = [30, 100, 300]
        self.staffNums = self.rng.randint(maxStaffs[self.corporateClass]-20, maxStaffs[self.corporateClass])

        print(f"Tag: {self.tag}, Reputation: {self.reputation}, Staffs: {self.staffNums} staffs created:\n\n")

        for _ in range(self.staffNums):
            # 회사 태그를 개발자의 career에 추가하도록 Developer 생성자에 전달
            dev_instance = Developer(
                True, self.reputation, company_tag=self.tag,
                tag=self.dev_ids.next() if self.dev_ids else None,
                rng=self.rng)
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