from itertools import zip_longest
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 웹드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 웹 페이지 열기
url = "https://www.trenbe.com/MEN/CLOTHING/%EC%85%94%EC%B8%A0?brandType=0&"
driver.get(url)
time.sleep(5)  # 페이지 로딩 대기

# 자동 스크롤 함수
def scroll_to_bottom(driver, pause_time=2):
    """웹 페이지 끝까지 스크롤합니다."""
    last_height = driver.execute_script("return document.body.scrollHeight")  # 초기 페이지 높이

    while True:
        # 페이지 끝까지 스크롤
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)  # 로딩 대기

        # 스크롤 후 새 페이지 높이 가져오기
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:  # 더 이상 스크롤되지 않으면 종료
            break
        last_height = new_height

def get_data_from_detail_page(driver, detail_page_url, existing_titles):
    """
    상세 페이지에서 브랜드, 제목, 가격, 이미지 정보를 가져옵니다.
    """
    driver.get(detail_page_url)
    time.sleep(3)  # 페이지 로딩 대기

    # 결과를 저장할 딕셔너리
    product_data = {
        "detail_page_url": detail_page_url,
        "brand": None,
        "title": None,
        "price": None,
        "images": []
    }

    try:
        # 1. 해당 클래스 이름을 기준으로 감싸져 있는 div 태그를 찾습니다.
        product_info_wrapper = driver.find_element(
            By.XPATH,
            "//div[contains(@class, 'ProductDetailTopInfo__ProductDetailTopWrapper-sc-13fomji-0 kFdCkC ProductDesktop__ProductDetailTopInfoOnDesktop-sc-1kh38dh-1')]"
        )

        # 2. 브랜드 정보 추출 (button 태그 내에서)
        brand_element = product_info_wrapper.find_element(
            By.XPATH,
            ".//button[contains(@class, 'Button__StyledButton-jc2t4o-0 bGFNwp tb-button tb-button-lg tb-button-text-dark tb-button-bold tb-button-rounded tb-button-filled text-button mb-4 lh-24p')]"
        )
        product_data["brand"] = brand_element.text.strip() if brand_element else None

        # 3. 제목 정보 추출 (p 태그 내에서)
        title_element = product_info_wrapper.find_element(
            By.CLASS_NAME, "product-detail-top__title"
        )
        title = title_element.text.strip() if title_element else None
        if title in existing_titles:  # 중복 제목 방지
            print(f"Duplicate title found: {title}")
            return None
        product_data["title"] = title
        existing_titles.add(title)  # 제목 기록

        # 4. 가격 정보 추출 (div 태그 내에서, span 태그의 클래스)
        price_wrapper = product_info_wrapper.find_element(
            By.XPATH,
            ".//div[contains(@class, 'ProductDetailTopPrice__Box-cg7axu-0 bMTmNx mt-10')]"
        )
        price_element = price_wrapper.find_element(
            By.XPATH,
            ".//span[contains(@class, 'font14 pc-font16 gray300')]"
        )
        product_data["price"] = price_element.text.strip() if price_element else None

        # 이미지 정보 추출
        carousel_images = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'Carousel__AliceItemImageWrap-sc-1fgnx5j-4')]//img"
        )
        seen_images = set()  # 중복 이미지 추적
        for img in carousel_images:
            src = img.get_attribute("src")
            if not src:  # src가 없으면 저장하지 않음
                print(f"Skipping image due to missing src.")
                continue
            if src in seen_images:  # 중복 이미지 방지
                print(f"Duplicate image found: {src}")
                continue

            # 이미지 크기 정보
            intrinsic_width = driver.execute_script("return arguments[0].naturalWidth;", img)
            intrinsic_height = driver.execute_script("return arguments[0].naturalHeight;", img)

            seen_images.add(src)
            product_data["images"].append({
                "src": src,
                "intrinsic_size": {"width": intrinsic_width, "height": intrinsic_height},
            })

        # 빈 값이거나 null인 항목은 저장하지 않도록 필터링
        if not all(value for value in product_data.values()):
            print(f"Skipping product due to missing data: {detail_page_url}")
            return None  # 데이터가 하나라도 비어있으면 None 반환

    except Exception as e:
        print(f"Error fetching data from detail page {detail_page_url}: {e}")
        return None  # 예외가 발생하면 None 반환

    return product_data



# 페이지 네이게이션 및 데이터 수집
def paginate(driver, combined_data, max_id=200):
    current_page = 1  # 시작 페이지
    start_id = 1  # id 시작 값
    existing_titles = set()  # 제목 중복 방지용

    while True:
        # 페이지 URL 생성
        page_url = f"{url}&page={current_page}"
        driver.get(page_url)
        time.sleep(5)  # 페이지 로딩 대기

        # 스크롤 추가
        scroll_to_bottom(driver, pause_time=2)

        # 상세 페이지 링크 추출
        detail_link_class_name = "ProductCard__ProductCardLink-sc-16qvrdv-0"  # 상세 페이지 링크 클래스 이름
        detail_links = driver.find_elements(By.XPATH, f"//a[contains(@class, '{detail_link_class_name}')]")
        detail_page_urls = [
            link.get_attribute("href") if link.get_attribute("href").startswith("http") else "https://www.trenbe.com" + link.get_attribute("href")
            for link in detail_links if link.get_attribute("href")
        ]
        print(f"Detail page URLs: {detail_page_urls}")
        
        # 데이터 수집
        for index, detail_url in enumerate(detail_page_urls, start=start_id):
            # 상세 페이지에서 데이터 가져오기
            product_data = get_data_from_detail_page(driver, detail_url, existing_titles)
            if product_data:
                product_data["id"] = index
                combined_data.append(product_data)

            # 최대 id 수에 도달하면 종료
            if index >= max_id:
                print(f"Reached max id limit of {max_id}. Stopping pagination.")
                return

        # 페이지가 끝나면 더 이상 데이터가 없으면 종료
        if not detail_page_urls:
            print(f"No data found on page {current_page}. Stopping pagination.")
            break

        current_page += 1
        start_id = combined_data[-1]["id"] + 1  # id 갱신

# 초기 데이터 수집 및 저장
combined_data = []
paginate(driver, combined_data)

# 웹 드라이버 종료
driver.quit()

# 데이터 저장
total_count = len(combined_data)
data_to_save = {
    "total_count": total_count,
    "combined_data": combined_data
}

# 결과를 JSON 파일로 저장
def save_data_to_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

save_data_to_json(data_to_save, "Shirts.json")

# 13번 라인 url 수정 187번 라인 파일명 알맞게