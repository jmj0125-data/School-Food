
import streamlit as st
import pandas as pd
import requests
import re
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
from collections import Counter


# ========================================
# 기본 설정
# ========================================
st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍚",
    layout="wide"
)

BASE_URL = "https://open.neis.go.kr/hub"
KST = ZoneInfo("Asia/Seoul")


# ========================================
# 함수: 줄임말 검색어 만들기
# ========================================
def make_search_variants(name):
    name = name.strip()
    variants = []

    if "여고" in name:
        variants.append(name.replace("여고", "여자고등학교"))

    if name.endswith("고"):
        variants.append(name[:-1] + "고등학교")

    result = []

    for value in variants:
        if value != name and value not in result:
            result.append(value)

    return result


# ========================================
# 학교 검색
# ========================================
@st.cache_data(ttl=600)
def search_schools(school_name):
    url = f"{BASE_URL}/schoolInfo"

    params = {
        "Type": "json",
        "SCHUL_NM": school_name
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        return [], "NETWORK_ERROR"

    except ValueError:
        return [], "JSON_ERROR"

    school_info = data.get("schoolInfo", [])

    if len(school_info) >= 2:
        rows = school_info[1].get("row", [])

        if rows:
            return rows, None

    return [], "INFO-200"


# ========================================
# 학교 검색 + 줄임말 재검색
# ========================================
def find_schools_with_fallback(name):
    schools, error = search_schools(name)

    if schools:
        return schools, name

    for variant in make_search_variants(name):
        schools, error = search_schools(variant)

        if schools:
            return schools, variant

    return [], None


# ========================================
# 한 달의 급식 조회
# ========================================
@st.cache_data(ttl=600)
def get_month_meals(
    education_code,
    school_code,
    start_date,
    end_date
):
    url = f"{BASE_URL}/mealServiceDietInfo"

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": education_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": start_date,
        "MLSV_TO_YMD": end_date,
        "pSize": 1000,
        "pIndex": 1
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        return [], "NETWORK_ERROR"

    except ValueError:
        return [], "JSON_ERROR"

    meal_info = data.get("mealServiceDietInfo", [])

    if len(meal_info) >= 2:
        rows = meal_info[1].get("row", [])

        if rows:
            return rows, None

    return [], "INFO-200"


# ========================================
# 메뉴 이름 정리
# ========================================
def clean_menu_item(item):
    """
    메뉴 뒤의 알레르기 번호를 제거하고
    통계에 사용할 반찬 이름으로 정리한다.

    예:
    김치(5.6.9) -> 김치
    계란말이(1.5) -> 계란말이
    """
    item = item.strip()

    if not item:
        return ""

    # 알레르기 번호 제거
    item = re.sub(
        r"\s*\([0-9.,]+\)\s*$",
        "",
        item
    )

    # 앞뒤 특수문자와 공백 정리
    item = item.strip(" -·")

    return item.strip()


# ========================================
# 메뉴에서 반찬 추출
# ========================================
def extract_side_dishes(menu):
    """
    NEIS 메뉴 문자열을 받아 메뉴 항목별로 나눈다.

    밥, 국, 찌개 등도 일단 메뉴 항목으로 들어올 수 있으므로
    기본적인 주식/국류는 통계에서 제외한다.
    """

    if not menu:
        return []

    # <br/>, <br>, <br /> 모두 처리
    items = re.split(
        r"<br\s*/?>",
        menu,
        flags=re.IGNORECASE
    )

    cleaned = []

    # 통계에서 제외할 대표적인 주식/국류
    exclude_words = [
        "밥",
        "국",
        "탕",
        "찌개",
        "죽",
        "면",
        "우동",
        "라면",
        "카레",
        "덮밥",
        "볶음밥",
        "비빔밥"
    ]

    for item in items:
        item = re.sub(r"<[^>]+>", "", item)
        item = clean_menu_item(item)

        if not item:
            continue

        # 주식/국류 제외
        if any(
            item == word or item.endswith(word)
            for word in exclude_words
        ):
            continue

        cleaned.append(item)

    return cleaned


# ========================================
# 한 학교의 한 달 반찬 빈도 계산
# ========================================
def count_school_side_dishes(meals):
    counter = Counter()

    for meal in meals:
        menu = meal.get("DDISH_NM", "")

        # 한 날짜에 같은 반찬이 두 번 적혀 있어도
        # '나온 날' 기준으로 한 번만 센다.
        dishes = set(extract_side_dishes(menu))

        for dish in dishes:
            counter[dish] += 1

    return counter


# ========================================
# 세션 상태
# ========================================
if "selected_schools" not in st.session_state:
    st.session_state.selected_schools = []

if "school_search_results" not in st.session_state:
    st.session_state.school_search_results = []


# ========================================
# 사이드바
# ========================================
st.sidebar.title("🍚 학교 급식 찾아보기")

page = st.sidebar.radio(
    "페이지",
    [
        "오늘 급식",
        "학교별 반찬 통계"
    ]
)


# ========================================
# 페이지 1: 오늘 급식
# ========================================
if page == "오늘 급식":

    st.title("학교 급식 찾아보기")
    st.write(
        "학교를 검색하고 날짜를 선택하면 "
        "그날의 중식 메뉴를 확인할 수 있습니다."
    )

    st.subheader("학교 찾기")

    with st.form("school_search_form"):
        school_name = st.text_input(
            "학교 이름",
            placeholder="예: 수도여고, 서울고, 한빛중학교"
        )

        search_button = st.form_submit_button(
            "학교 찾기",
            type="primary"
        )

    if search_button:
        school_name = school_name.strip()

        if not school_name:
            st.warning("학교 이름을 입력해 주세요.")

        else:
            schools, used_name = find_schools_with_fallback(
                school_name
            )

            if schools:
                st.session_state.school_search_results = schools

                if used_name != school_name:
                    st.info(
                        f"'{school_name}'으로 찾을 수 없어 "
                        f"'{used_name}'으로 다시 검색했습니다."
                    )

            else:
                st.session_state.school_search_results = []

                st.error(
                    f"'{school_name}'에 해당하는 학교를 "
                    "찾지 못했습니다."
                )

    if st.session_state.school_search_results:

        schools = st.session_state.school_search_results

        options = []

        for i, school in enumerate(schools):
            label = (
                f"{school.get('SCHUL_NM', '')} "
                f"({school.get('LCTN_SC_NM', '')})"
            )

            options.append(label)

        selected_index = st.selectbox(
            "학교를 선택하세요.",
            range(len(schools)),
            format_func=lambda i: options[i]
        )

        selected_school = schools[selected_index]

        st.caption(
            f"선택한 학교: "
            f"{selected_school.get('SCHUL_NM', '')} · "
            f"{selected_school.get('LCTN_SC_NM', '')}"
        )

        st.subheader("급식 날짜")

        today = datetime.now(KST).date()

        selected_date = st.date_input(
            "날짜",
            value=today
        )

        date_string = selected_date.strftime("%Y%m%d")

        if st.button("중식 확인", type="primary"):

            rows, error = get_month_meals(
                selected_school.get("ATPT_OFCDC_SC_CODE"),
                selected_school.get("SD_SCHUL_CODE"),
                date_string,
                date_string
            )

            if not rows:
                st.info(
                    f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                    "등록된 중식 급식이 없습니다."
                )

            else:
                meal = rows[0]

                menu = meal.get("DDISH_NM", "")
                menu = re.sub(
                    r"<br\s*/?>",
                    "\n",
                    menu,
                    flags=re.IGNORECASE
                )

                menu = re.sub(
                    r"<[^>]+>",
                    "",
                    menu
                )

                st.subheader(
                    f"🍚 {selected_date.strftime('%Y년 %m월 %d일')} 중식"
                )

                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown("### 메뉴")
                    st.text(menu)

                with col2:
                    st.markdown("### 칼로리")
                    st.metric(
                        "열량",
                        meal.get("CAL_INFO", "정보 없음")
                    )

                st.caption(
                    "※ 메뉴 뒤 괄호의 숫자는 알레르기 유발 "
                    "식품 번호입니다."
                )


