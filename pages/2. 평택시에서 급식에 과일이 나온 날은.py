import streamlit as st
import requests
import pandas as pd
import re
import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo


# ========================================
# 페이지 설정
# ========================================
st.set_page_config(
    page_title="급식에 과일이 나온 날은",
    page_icon="🍎",
    layout="wide"
)

st.title("급식에 과일이 나온 날은 🍎")
st.write(
    "학교를 여러 개 선택하고 한 달을 고르면 "
    "과일이 나온 날을 학교별로 확인할 수 있습니다."
)

BASE_URL = "https://open.neis.go.kr/hub"
KST = ZoneInfo("Asia/Seoul")


# ========================================
# 학교 이름 검색
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
        return []

    except ValueError:
        return []

    school_info = data.get("schoolInfo", [])

    if len(school_info) >= 2:
        return school_info[1].get("row", [])

    return []


# ========================================
# 줄임말을 풀어서 검색
# ========================================
def search_schools_with_fallback(name):

    # 1차 검색
    schools = search_schools(name)

    if schools:
        return schools

    # 여고 → 여자고등학교
    if "여고" in name:
        new_name = name.replace(
            "여고",
            "여자고등학교"
        )

        schools = search_schools(new_name)

        if schools:
            return schools

    # 끝의 고 → 고등학교
    if name.endswith("고"):
        new_name = name[:-1] + "고등학교"

        schools = search_schools(new_name)

        if schools:
            return schools

    return []


# ========================================
# 한 달 급식 조회
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
        return []

    except ValueError:
        return []

    meal_info = data.get(
        "mealServiceDietInfo",
        []
    )

    if len(meal_info) >= 2:
        return meal_info[1].get(
            "row",
            []
        )

    return []


# ========================================
# 과일 목록
# ========================================
FRUITS = [
    "사과",
    "배",
    "귤",
    "오렌지",
    "자몽",
    "레몬",
    "바나나",
    "포도",
    "청포도",
    "샤인머스켓",
    "딸기",
    "수박",
    "참외",
    "멜론",
    "복숭아",
    "자두",
    "살구",
    "키위",
    "파인애플",
    "망고",
    "파파야",
    "석류",
    "블루베리",
    "체리",
    "토마토",
    "방울토마토",
    "과일"
]


# ========================================
# 과일이 포함되어 있는지 확인
# ========================================
def find_fruits(menu):

    if not menu:
        return []

    # <br/>를 구분자로 변경
    menu = re.sub(
        r"<br\s*/?>",
        "\n",
        menu,
        flags=re.IGNORECASE
    )

    # HTML 제거
    menu = re.sub(
        r"<[^>]+>",
        "",
        menu
    )

    lines = menu.split("\n")

    found = []

    for line in lines:

        # 알레르기 번호 제거
        clean_line = re.sub(
            r"\s*\([0-9.,]+\)",
            "",
            line
        ).strip()

        for fruit in FRUITS:

            if fruit in clean_line:

                if fruit not in found:
                    found.append(fruit)

    return found


# ========================================
# 세션 상태
# ========================================
if "school_search_results" not in st.session_state:
    st.session_state.school_search_results = []

if "selected_schools" not in st.session_state:
    st.session_state.selected_schools = []


# ========================================
# 1. 학교 찾기
# ========================================
st.subheader("1. 학교 찾기")

with st.form("school_search"):

    school_name = st.text_input(
        "학교 이름",
        placeholder="예: 수도여고, 서울고, 평택고"
    )

    search_button = st.form_submit_button(
        "학교 찾기",
        type="primary"
    )


if search_button:

    school_name = school_name.strip()

    if not school_name:

        st.warning(
            "학교 이름을 입력해 주세요."
        )

    else:

        schools = search_schools_with_fallback(
            school_name
        )

        if schools:

            st.session_state.school_search_results = schools

        else:

            st.session_state.school_search_results = []

            st.warning(
                f"'{school_name}'에 해당하는 학교를 "
                "찾지 못했습니다."
            )


# ========================================
# 2. 학교 선택
# ========================================
if st.session_state.school_search_results:

    st.subheader("2. 학교 선택")

    schools = st.session_state.school_search_results

    school_options = []

    for i, school in enumerate(schools):

        school_options.append(
            f"{school.get('SCHUL_NM', '')} "
            f"({school.get('LCTN_SC_NM', '')})"
        )

    selected_indices = st.multiselect(
        "비교할 학교를 선택하세요.",
        range(len(schools)),
        format_func=lambda i: school_options[i]
    )

    if st.button("선택한 학교 추가"):

        for index in selected_indices:

            school = schools[index]

            school_key = (
                school.get(
                    "ATPT_OFCDC_SC_CODE"
                ),
                school.get(
                    "SD_SCHUL_CODE"
                )
            )

            exists = False

            for selected in st.session_state.selected_schools:

                selected_key = (
                    selected.get(
                        "ATPT_OFCDC_SC_CODE"
                    ),
                    selected.get(
                        "SD_SCHUL_CODE"
                    )
                )

                if school_key == selected_key:
                    exists = True
                    break

            if not exists:
                st.session_state.selected_schools.append(
                    school
                )

        st.rerun()


# ========================================
# 선택된 학교 목록
# ========================================
if st.session_state.selected_schools:

    st.subheader("3. 선택된 학교")

    for i, school in enumerate(
        st.session_state.selected_schools
    ):

        col1, col2 = st.columns([5, 1])

        with col1:

            st.write(
                f"**{school.get('SCHUL_NM', '')}** "
                f"({school.get('LCTN_SC_NM', '')})"
            )

        with col2:

            if st.button(
                "삭제",
                key=f"remove_{i}"
            ):

                st.session_state.selected_schools.pop(i)

                st.rerun()


    # ====================================
    # 4. 조회할 달
    # ====================================
    st.subheader("4. 조회할 달")

    today = datetime.now(KST).date()

    col1, col2 = st.columns(2)

    with col1:

        year = st.number_input(
            "연도",
            min_value=2020,
            max_value=today.year,
            value=today.year,
            step=1
        )

    with col2:

        month = st.selectbox(
            "월",
            range(1, 13),
            index=today.month - 1,
            format_func=lambda x: f"{x}월"
        )


    # ====================================
    # 날짜 범위
    # ====================================
    last_day = calendar.monthrange(
        int(year),
        int(month)
    )[1]

    start_date = date(
        int(year),
        int(month),
        1
    )

    end_date = date(
        int(year),
        int(month),
        last_day
    )


    # ====================================
    # 5. 과일 나온 날 찾기
    # ====================================
    if st.button(
        "과일이 나온 날 찾기",
        type="primary"
    ):

        results = []

        progress = st.progress(0)

        total = len(
            st.session_state.selected_schools
        )

        for index, school in enumerate(
            st.session_state.selected_schools
        ):

            rows = get_month_meals(
                school.get(
                    "ATPT_OFCDC_SC_CODE"
                ),
                school.get(
                    "SD_SCHUL_CODE"
                ),
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d")
            )

            for meal in rows:

                menu = meal.get(
                    "DDISH_NM",
                    ""
                )

                fruits = find_fruits(menu)

                if fruits:

                    results.append(
                        {
                            "학교": school.get(
                                "SCHUL_NM",
                                ""
                            ),
                            "지역": school.get(
                                "LCTN_SC_NM",
                                ""
                            ),
                            "날짜": pd.to_datetime(
                                meal.get(
                                    "MLSV_YMD"
                                ),
                                format="%Y%m%d",
                                errors="coerce"
                            ),
                            "과일": ", ".join(
                                fruits
                            )
                        }
                    )

            progress.progress(
                (index + 1) / total
            )

        progress.empty()


        # ====================================
        # 결과 표시
        # ====================================
        if not results:

            st.info(
                f"{year}년 {month}월에는 "
                "선택한 학교의 급식에서 과일이 나온 날을 "
                "찾지 못했습니다."
            )

        else:

            result_df = pd.DataFrame(
                results
            )

            # 학교별 → 날짜순
            result_df = result_df.sort_values(
                by=[
                    "학교",
                    "날짜"
                ],
                ascending=[
                    True,
                    True
                ]
            )

            result_df["날짜"] = result_df[
                "날짜"
            ].dt.strftime(
                "%Y년 %m월 %d일"
            )

            st.subheader(
                f"🍎 {year}년 {month}월 "
                "과일이 나온 날"
            )

            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True
            )

            # =================================
            # 학교별 과일 나온 횟수
            # =================================
            st.subheader("학교별 과일 급식 횟수")

            summary = (
                result_df
                .groupby(
                    ["학교", "지역"],
                    as_index=False
                )
                .size()
                .rename(
                    columns={
                        "size": "과일이 나온 날"
                    }
                )
            )

            summary = summary.sort_values(
                "과일이 나온 날",
                ascending=False
            )

            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True
            )

else:

    st.info(
        "먼저 학교를 검색해서 비교할 학교를 추가해 주세요."
    )
