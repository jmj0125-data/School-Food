import streamlit as st
import requests
import re
from datetime import datetime
from zoneinfo import ZoneInfo


# ----------------------------------------
# 기본 설정
# ----------------------------------------
st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍚",
    layout="wide"
)

st.title("학교 급식 찾아보기")
st.write("학교를 검색하고 날짜를 선택하면 그날의 중식 메뉴를 확인할 수 있습니다.")

BASE_URL = "https://open.neis.go.kr/hub"

# 한국 시간
KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()


# ----------------------------------------
# 학교 이름 검색어 변환
# ----------------------------------------
def make_search_variants(name):
    """
    입력한 학교 이름으로 검색했는데 결과가 없을 때
    줄임말을 풀어서 다시 검색할 검색어를 만든다.
    """
    name = name.strip()
    variants = []

    # 여고 → 여자고등학교
    if "여고" in name:
        variants.append(name.replace("여고", "여자고등학교"))

    # 학교 이름 끝의 '고' → '고등학교'
    # 예: 수도고 → 수도고등학교
    if name.endswith("고"):
        variants.append(name[:-1] + "고등학교")

    # 혹시 중복이 생기지 않도록 정리
    result = []
    for value in variants:
        if value != name and value not in result:
            result.append(value)

    return result


# ----------------------------------------
# 학교 정보 API
# ----------------------------------------
@st.cache_data(ttl=600)
def search_schools(school_name):
    url = f"{BASE_URL}/schoolInfo"

    params = {
        "Type": "json",
        "SCHUL_NM": school_name
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return [], "NETWORK_ERROR"
    except ValueError:
        return [], "JSON_ERROR"

    # 정상적인 학교 정보가 있는 경우
    school_info = data.get("schoolInfo", [])

    if len(school_info) >= 2:
        rows = school_info[1].get("row", [])
        if rows:
            return rows, None

    # 조회 결과 없음
    return [], "INFO-200"


def find_schools_with_fallback(name):
    """
    원래 검색어로 먼저 검색하고,
    결과가 없으면 줄임말을 풀어서 다시 검색한다.
    """
    schools, error = search_schools(name)

    if schools:
        return schools, name

    # 줄임말을 풀어 한 번 더 검색
    for variant in make_search_variants(name):
        schools, error = search_schools(variant)

        if schools:
            return schools, variant

    return [], None


# ----------------------------------------
# 급식 API
# ----------------------------------------
@st.cache_data(ttl=300)
def get_lunch(education_code, school_code, date_string):
    url = f"{BASE_URL}/mealServiceDietInfo"

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": education_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_string,
        "MLSV_TO_YMD": date_string,
        "pSize": 1000,
        "pIndex": 1
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None, "NETWORK_ERROR"
    except ValueError:
        return None, "JSON_ERROR"

    meal_info = data.get("mealServiceDietInfo", [])

    if len(meal_info) >= 2:
        rows = meal_info[1].get("row", [])

        if rows:
            return rows, None

    # 급식 데이터가 없는 경우
    return [], "INFO-200"


# ----------------------------------------
# 세션 상태
# ----------------------------------------
if "schools" not in st.session_state:
    st.session_state.schools = []

if "search_name" not in st.session_state:
    st.session_state.search_name = ""


# ----------------------------------------
# 학교 검색
# ----------------------------------------
st.subheader("1. 학교 찾기")

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
        st.session_state.schools = []
    else:
        schools, used_name = find_schools_with_fallback(school_name)

        if schools:
            st.session_state.schools = schools
            st.session_state.search_name = school_name

            if used_name != school_name:
                st.info(
                    f"'{school_name}'으로 찾을 수 없어 "
                    f"'{used_name}'으로 다시 검색했습니다."
                )
        else:
            st.session_state.schools = []
            st.session_state.search_name = school_name
            st.error(
                f"'{school_name}'에 해당하는 학교를 찾지 못했습니다. "
                "학교 이름을 다시 확인해 주세요."
            )


# ----------------------------------------
# 학교 선택
# ----------------------------------------
if st.session_state.schools:
    st.subheader("2. 학교 선택")

    schools = st.session_state.schools

    # 같은 이름의 학교가 있을 수 있으므로
    # 학교명 + 지역을 함께 표시
    school_options = []

    for school in schools:
        school_name_value = school.get("SCHUL_NM", "")
        region = school.get("LCTN_SC_NM", "")

        label = f"{school_name_value} ({region})"
        school_options.append(label)

    selected_index = st.selectbox(
        "검색된 학교 중 하나를 선택하세요.",
        range(len(schools)),
        format_func=lambda i: school_options[i]
    )

    selected_school = schools[selected_index]

    selected_school_name = selected_school.get("SCHUL_NM", "")
    selected_region = selected_school.get("LCTN_SC_NM", "")
    education_code = selected_school.get("ATPT_OFCDC_SC_CODE", "")
    school_code = selected_school.get("SD_SCHUL_CODE", "")

    st.caption(
        f"선택한 학교: {selected_school_name} · {selected_region}"
    )

    # ----------------------------------------
    # 날짜 선택
    # ----------------------------------------
    st.subheader("3. 급식 날짜 선택")

    selected_date = st.date_input(
        "날짜",
        value=today_kst,
        key="meal_date"
    )

    date_string = selected_date.strftime("%Y%m%d")

    # ----------------------------------------
    # 급식 조회
    # ----------------------------------------
    if st.button("중식 확인", type="primary"):
        rows, error = get_lunch(
            education_code,
            school_code,
            date_string
        )

        if error == "INFO-200" or not rows:
            st.info(
                f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                "등록된 중식 급식이 없습니다."
            )

        elif error == "NETWORK_ERROR":
            st.error(
                "급식 정보를 가져오는 중 네트워크 오류가 발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

        elif error == "JSON_ERROR":
            st.error(
                "급식 정보를 읽는 중 오류가 발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

        else:
            # 해당 날짜의 중식 데이터
            meal = rows[0]

            menu = meal.get("DDISH_NM", "")
            calories = meal.get("CAL_INFO", "")

            # NEIS의 <br/>를 실제 줄바꿈으로 변경
            menu = re.sub(r"<br\s*/?>", "\n", menu, flags=re.IGNORECASE)

            # 혹시 남아 있는 HTML 태그 제거
            menu = re.sub(r"<[^>]+>", "", menu)

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
                    calories if calories else "정보 없음"
                )

            st.caption(
                "※ 메뉴 뒤 괄호의 숫자는 알레르기 유발 식품 번호입니다."
            )

