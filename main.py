from developer import Developer
from company import Corporate
import json # json 모듈 임포트


if __name__ == "__main__":
    print("Main Activated")
    
    # 회사 생성 예시
    print("\n--- Creating Companies ---")
    company1 = Corporate(0) # 첫 번째 회사 (C01)
    company2 = Corporate(1) # 두 번째 회사 (C02)
    company3 = Corporate(2) # 세 번째 회사 (C03)

    # 독립적인 개발자 생성 예시
    print("\n--- Creating Standalone Developers ---")
    dev_a = Developer(True, 5000) # 독립 개발자 A
    dev_b = Developer(False, 1000) # 독립 개발자 B

    print("\n--- Accessing Objects by Tag (O(1) Access) ---")
    # 태그를 사용하여 회사 객체에 O(1)로 접근
    if "C01" in Corporate.all_companies:
        retrieved_company = Corporate.all_companies["C01"]
        print(f"Retrieved Company C01: {retrieved_company.corporateName}, Reputation: {retrieved_company.reputation}")
    
    # 태그를 사용하여 개발자 객체에 O(1)로 접근
    # dev_a의 정확한 태그는 이전에 생성된 회사들의 직원 수에 따라 달라질 수 있습니다.
    # 여기서는 dev_a 객체 자체가 가지고 있는 tag 속성을 사용합니다.
    if dev_a.tag in Developer.all_developers:
        retrieved_developer = Developer.all_developers[dev_a.tag]
        print(f"Retrieved Developer {retrieved_developer.tag}: {retrieved_developer.first_name} {retrieved_developer.last_name}, Education: {retrieved_developer.education}")

    print("\n--- All Created Tags ---")
    print("All Company Tags:", list(Corporate.all_companies.keys()))
    print("All Developer Tags:", list(Developer.all_developers.keys()))

    print("\n--- Saving Data to JSON ---")
    
    # 회사 데이터 직렬화 및 저장
    all_corporate_data = []
    for company_tag, company_obj in Corporate.all_companies.items():
        all_corporate_data.append(company_obj.to_dict())
    
    with open("corporate.json", "w", encoding="utf-8") as f:
        json.dump(all_corporate_data, f, indent=4, ensure_ascii=False)
    print("corporate.json saved.")

    # 개발자 데이터 직렬화 및 저장
    all_developer_data = []
    for dev_tag, dev_obj in Developer.all_developers.items():
        all_developer_data.append(dev_obj.to_dict())

    with open("dev.json", "w", encoding="utf-8") as f:
        json.dump(all_developer_data, f, indent=4, ensure_ascii=False)
    print("dev.json saved.")