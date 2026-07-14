import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(
    page_title="우리 동네 쌍둥이 지역 찾기",
    page_icon="👥",
    layout="wide"
)

st.title("👥 우리 동네와 인구 구조가 가장 비슷한 '쌍둥이' 지역 찾기")
st.markdown("""
이 서비스는 입력하신 지역의 연령별 인구 비율과 **가장 유사한 인구 구조**를 가진 쌍둥이 지역을 찾아주는 서비스입니다.
""")

# 데이터 로드 및 전처리 캐싱
@st.cache_data
def load_data():
    file_path = "202606_202606_연령별인구현황_월간.csv"
    try:
        # CP949 인코딩으로 데이터 읽기
        df = pd.read_csv(file_path, encoding='cp949')
    except UnicodeDecodeError:
        # 에러 발생 시 UTF-8-sig 시도
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    
    # 1. 행정구역명을 깔끔하게 정리 (예: "서울특별시  (1100000000)" -> "서울특별시")
    df['행정구역_정리'] = df['행정구역'].str.split('(').str[0].str.strip()
    
    # 2. 분석에 필요한 '계' 기준 연령별 컬럼 선택
    age_cols = [
        '2026년06월_계_0~9세', '2026년06월_계_10~19세', '2026년06월_계_20~29세',
        '2026년06월_계_30~39세', '2026년06월_계_40~49세', '2026년06월_계_50~59세',
        '2026년06월_계_60~69세', '2026년06월_계_70~79세', '2026년06월_계_80~89세',
        '2026년06월_계_90~99세', '2026년06월_계_100세 이상'
    ]
    
    # 데이터 타입 변환 및 콤마 제거
    for col in age_cols + ['2026년06월_계_총인구수']:
        df[col] = df[col].astype(str).str.replace(',', '').astype(float)
        
    # '전국' 행 제외 (순수 지역 간 비교를 위해)
    df = df[df['행정구역_정리'] != '전국'].reset_index(drop=True)
    
    # 각 연령대 비율(%) 계산
    for col in age_cols:
        rate_col_name = col.split('_')[-1] + ' 비율'
        df[rate_col_name] = (df[col] / df['2026년06월_계_총인구수']) * 100
        
    return df, [col.split('_')[-1] + ' 비율' for col in age_cols]

try:
    df, rate_cols = load_data()
    
    # ------------------ 사이드바: 지역 검색 및 선택 ------------------
    st.sidebar.header("🔍 지역 선택")
    search_query = st.sidebar.text_input("찾으려는 지역명을 입력하세요 (예: 역삼, 정자, 마포):", "")
    
    # 검색어 필터링
    if search_query:
        filtered_regions = df[df['행정구역_정리'].str.contains(search_query)]['행정구역_정리'].tolist()
    else:
        filtered_regions = df['행정구역_정리'].tolist()
        
    if not filtered_regions:
        st.sidebar.warning("💡 검색 결과가 없습니다. 다른 이름으로 검색해보세요.")
        selected_region = df['행정구역_정리'].iloc[0]
    else:
        selected_region = st.sidebar.selectbox("비교 기준 지역을 선택하세요:", filtered_regions)
        
    # ------------------ 쌍둥이 지역 알고리즘 연산 ------------------
    # 기준 지역의 비율 데이터 추출
    target_row = df[df['행정구역_정리'] == selected_region].iloc[0]
    target_rates = target_row[rate_cols].values.astype(float)
    
    # 모든 지역에 대해 제곱오차합(SSE) 계산
    all_rates = df[rate_cols].values.astype(float)
    sse = np.sum((all_rates - target_rates) ** 2, axis=1)
    
    df['차이값'] = sse
    
    # 자기 자신을 제외하고 가장 차이값이 작은(유사한) 상위 3개 지역 추출
    twins_df = df[df['행정구역_정리'] != selected_region].nsmallest(3, '차이값')
    best_twin = twins_df.iloc[0]
    
    # ------------------ 메인 대시보드 화면 구성 ------------------
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"📍 선택한 지역: {selected_region}")
        st.metric(label="총 인구수", value=f"{int(target_row['2026년06월_계_총인구수']):,} 명")
        
    with col2:
        st.subheader(f"👯 매칭된 No.1 쌍둥이 지역: {best_twin['행정구역_정리']}")
        st.metric(
            label="총 인구수", 
            value=f"{int(best_twin['2026년06월_계_총인구수']):,} 명",
            delta=f"{int(best_twin['2026년06월_계_총인구수'] - target_row['2026년06월_계_총인구수']):,} 명 (차이)"
        )

    st.markdown("---")
    
    # ------------------ Plotly 인터랙티브 그래프 그리기 ------------------
    st.subheader("📊 연령대별 인구 비율 분석")
    st.write("마우스를 그래프 위에 올리면 정확한 퍼센트(%) 비율을 확인할 수 있습니다.")
    
    # 연령대 축 레이블 간소화 (예: '0~9세 비율' -> '0~9세')
    x_labels = [col.replace(' 비율', '') for col in rate_cols]
    
    fig = go.Figure()
    
    # 1. 기준 지역 꺾은선 (영역 채우기 포함)
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=target_rates,
        mode='lines+markers',
        name=selected_region,
        line=dict(color='#1f77b4', width=4),
        marker=dict(size=8),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.15)',
        hovertemplate='%{x}: <b>%{y:.2f}%</b><extra></extra>'
    ))
    
    # 2. 1순위 쌍둥이 지역 꺾은선
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=best_twin[rate_cols].values.astype(float),
        mode='lines+markers',
        name=f"🥇 {best_twin['행정구역_정리']} (가장 비슷)",
        line=dict(color='#ff7f0e', width=3, dash='dash'),
        marker=dict(size=8),
        hovertemplate='%{x}: <b>%{y:.2f}%</b><extra></extra>'
    ))
    
    # 3. 2순위 쌍둥이 지역 꺾은선
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=twins_df.iloc[1][rate_cols].values.astype(float),
        mode='lines+markers',
        name=f"🥈 {twins_df.iloc[1]['행정구역_정리']}",
        line=dict(color='#2ca02c', width=2, dash='dot'),
        marker=dict(size=6),
        visible='legendonly', # 기본적으로는 가려두고 범례 클릭 시 표시
        hovertemplate='%{x}: <b>%{y:.2f}%</b><extra></extra>'
    ))

    # 레이아웃 정밀 튜닝
    fig.update_layout(
        title=dict(
            text=f"<b>'{selected_region}'</b> vs <b>'{best_twin['행정구역_정리']}'</b> 인구 구조 비교",
            font=dict(size=18)
        ),
        xaxis=dict(title="연령대", tickfont=dict(size=12)),
        yaxis=dict(title="인구 비율 (%)", ticksuffix="%", gridcolor='rgba(200, 200, 200, 0.3)'),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=80, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=550
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ------------------ 보조 정보 제공 테이블 ------------------
    st.markdown("---")
    st.subheader("📋 인구 구조 매칭 TOP 3 상세 데이터")
    
    # 시각화용 데이터프레임 가공
    display_cols = ['행정구역_정리', '2026년06월_계_총인구수'] + rate_cols
    display_df = pd.concat([pd.DataFrame([target_row]), twins_df])[display_cols]
    
    # 컬럼 이름 간소화 및 인덱스 리셋
    display_df.columns = ['지역명', '총인구수'] + x_labels
    display_df['총인구수'] = display_df['총인구수'].apply(lambda x: f"{int(x):,}")
    
    # 비율 데이터는 소수점 둘째자리까지 표기
    for col in x_labels:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%")
        
    st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

except FileNotFoundError:
    st.error("🚨 폴더 내에서 `'202606_202606_연령별인구현황_월간.csv'` 파일을 찾을 수 없습니다. 파일명을 확인해 주시거나 깃허브 저장소에 같은 이름으로 업로드되어 있는지 체크해 주세요!")
