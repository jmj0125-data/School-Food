
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


# ========================================
# 페이지 2: 학교별 반찬 통계
# ========================================
else:

    st.title("학교별 반찬 통계")

    st.write(
        "여러 학교를 선택하고 한 달 동안 "
        "적게 나온 반찬을 한눈에 비교해 보세요."
    )

    # ------------------------------------
    # 학교 검색
    # ------------------------------------
    st.subheader("학교 추가")

    with st.form("multi_school_search_form"):

        search_name = st.text_input(
            "학교 이름",
            placeholder="예: 수도여고"
        )

        search_button = st.form_submit_button(
            "학교 찾기"
        )

    if search_button:

        search_name = search_name.strip()

        if not search_name:
            st.warning("학교 이름을 입력해 주세요.")

        else:

            schools, used_name = find_schools_with_fallback(
                search_name
            )

            if schools:

                st.session_state.school_search_results = schools

                if used_name != search_name:
                    st.info(
                        f"'{search_name}'으로 찾을 수 없어 "
                        f"'{used_name}'으로 다시 검색했습니다."
                    )

            else:

                st.session_state.school_search_results = []

                st.warning(
                    f"'{search_name}'에 해당하는 학교를 "
                    "찾지 못했습니다."
                )

    # ------------------------------------
    # 검색 결과에서 학교 선택
    # ------------------------------------
    if st.session_state.school_search_results:

        schools = st.session_state.school_search_results

        options = []

        for i, school in enumerate(schools):

            options.append(
                f"{school.get('SCHUL_NM', '')} "
                f"({school.get('LCTN_SC_NM', '')})"
            )

        selected_indices = st.multiselect(
            "추가할 학교를 선택하세요.",
            range(len(schools)),
            format_func=lambda i: options[i]
        )

        if st.button("선택한 학교 추가"):

            for index in selected_indices:

                school = schools[index]

                school_key = (
                    school.get("ATPT_OFCDC_SC_CODE"),
                    school.get("SD_SCHUL_CODE")
                )

                already_added = False

                for existing in st.session_state.selected_schools:

                    existing_key = (
                        existing.get("ATPT_OFCDC_SC_CODE"),
                        existing.get("SD_SCHUL_CODE")
                    )

                    if existing_key == school_key:
                        already_added = True
                        break

                if not already_added:
                    st.session_state.selected_schools.append(
                        school
                    )

            st.rerun()

    # ------------------------------------
    # 선택된 학교
    # ------------------------------------
    if st.session_state.selected_schools:

        st.subheader("선택한 학교")

        # 학교를 작은 태그처럼 표시
        selected_names = []

        for school in st.session_state.selected_schools:

            selected_names.append(
                f"{school.get('SCHUL_NM', '')} "
                f"({school.get('LCTN_SC_NM', '')})"
            )

        st.info("  ·  ".join(selected_names))

        # 학교 삭제
        with st.expander("학교 목록 수정"):

            for i, school in enumerate(
                st.session_state.selected_schools
            ):

                col1, col2 = st.columns([5, 1])

                with col1:
                    st.write(
                        f"{school.get('SCHUL_NM', '')} "
                        f"({school.get('LCTN_SC_NM', '')})"
                    )

                with col2:

                    if st.button(
                        "삭제",
                        key=f"delete_school_{i}"
                    ):
                        st.session_state.selected_schools.pop(i)
                        st.rerun()

        # --------------------------------
        # 조회할 달
        # --------------------------------
        st.subheader("조회할 달")

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

        # --------------------------------
        # 통계 보기
        # --------------------------------
        if st.button(
            "📊 한 달 반찬 통계 보기",
            type="primary",
            use_container_width=True
        ):

            all_results = []

            progress = st.progress(0)

            total = len(
                st.session_state.selected_schools
            )

            for index, school in enumerate(
                st.session_state.selected_schools
            ):

                rows, error = get_month_meals(
                    school.get(
                        "ATPT_OFCDC_SC_CODE"
                    ),
                    school.get(
                        "SD_SCHUL_CODE"
                    ),
                    start_date.strftime("%Y%m%d"),
                    end_date.strftime("%Y%m%d")
                )

                counter = count_school_side_dishes(
                    rows
                )

                for dish, count in counter.items():

                    all_results.append(
                        {
                            "학교": school.get(
                                "SCHUL_NM",
                                ""
                            ),
                            "지역": school.get(
                                "LCTN_SC_NM",
                                ""
                            ),
                            "반찬": dish,
                            "나온 횟수": count
                        }
                    )

                progress.progress(
                    (index + 1) / total
                )

            progress.empty()

            # --------------------------------
            # 결과 없음
            # --------------------------------
            if not all_results:

                st.warning(
                    "선택한 학교에 해당 월의 "
                    "급식 데이터가 없습니다."
                )

            else:

                result_df = pd.DataFrame(
                    all_results
                )

                result_df = result_df.sort_values(
                    by=[
                        "학교",
                        "나온 횟수",
                        "반찬"
                    ],
                    ascending=[
                        True,
                        True,
                        True
                    ]
                ).reset_index(drop=True)

                # ==================================
                # 핵심 결과
                # ==================================
                st.divider()

                st.header(
                    f"🍽️ {year}년 {month}월 "
                    "적게 나온 반찬"
                )

                st.caption(
                    "각 반찬이 그 달의 급식 메뉴에 "
                    "등장한 날짜 수를 기준으로 정렬했습니다."
                )

                # --------------------------------
                # 학교별 카드
                # --------------------------------

                schools_list = (
                    result_df["학교"]
                    .drop_duplicates()
                    .tolist()
                )

                # 한 줄에 2개 학교
                for start in range(
                    0,
                    len(schools_list),
                    2
                ):

                    row_schools = schools_list[
                        start:start + 2
                    ]

                    columns = st.columns(
                        len(row_schools)
                    )

                    for col, school_name in zip(
                        columns,
                        row_schools
                    ):

                        with col:

                            school_df = result_df[
                                result_df["학교"]
                                == school_name
                            ].copy()

                            region = school_df.iloc[0][
                                "지역"
                            ]

                            # 등장 횟수별로 묶는다.
                            # 예: 1회인 반찬이 여러 개면
                            # 같은 순위로 표시
                            counts = sorted(
                                school_df[
                                    "나온 횟수"
                                ].unique()
                            )

                            top_counts = counts[:5]

                            st.markdown(
                                f"### 🏫 {school_name}"
                            )

                            st.caption(region)

                            # 카드 느낌의 컨테이너
                            with st.container(
                                border=True
                            ):

                                rank = 1

                                for count in top_counts:

                                    dishes = school_df[
                                        school_df[
                                            "나온 횟수"
                                        ] == count
                                    ]["반찬"].tolist()

                                    dish_text = ", ".join(
                                        dishes
                                    )

                                    st.markdown(
                                        f"**{rank}위**  "
                                        f"{dish_text}"
                                    )

                                    st.caption(
                                        f"{count}회 나옴"
                                    )

                                    rank += 1

                # ==================================
                # 학교별 최저 빈도만 한눈에
                # ==================================
                st.divider()

                st.header(
                    "🔎 학교별 가장 적게 나온 반찬"
                )

                summary_columns = st.columns(
                    min(
                        3,
                        len(schools_list)
                    )
                )

                for i, school_name in enumerate(
                    schools_list
                ):

                    school_df = result_df[
                        result_df["학교"]
                        == school_name
                    ]

                    min_count = school_df[
                        "나온 횟수"
                    ].min()

                    rare_dishes = school_df[
                        school_df["나온 횟수"]
                        == min_count
                    ]["반찬"].tolist()

                    region = school_df.iloc[0][
                        "지역"
                    ]

                    with summary_columns[
                        i % len(summary_columns)
                    ]:

                        with st.container(
                            border=True
                        ):

                            st.markdown(
                                f"### {school_name}"
                            )

                            st.caption(region)

                            st.metric(
                                "가장 적게 나온 횟수",
                                f"{min_count}회"
                            )

                            st.write(
                                " · ".join(
                                    rare_dishes
                                )
                            )

                # ==================================
                # 전체 목록
                # ==================================
                st.divider()

                with st.expander(
                    "📋 전체 반찬 등장 횟수 보기"
                ):

                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True
                    )

    else:

        st.info(
            "먼저 학교를 검색해서 비교할 학교를 추가해 주세요."
        )
