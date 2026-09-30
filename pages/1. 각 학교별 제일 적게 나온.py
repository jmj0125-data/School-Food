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
