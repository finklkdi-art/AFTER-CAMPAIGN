---
name: report-design-system
description: 삼성전자 캠페인 결과보고 PPTX의 실측 디자인 시스템 — 좌표·타이포(SAMSUNG SS 7종)·컬러·표/차트/컴포넌트 규격과 페이지별 레퍼런스 계보. 결과리포트 슬라이드를 만들거나 고칠 때, theme.py·blocks.py·renderer.py 를 건드릴 때, 새 슬라이드 블록·아키타입을 추가할 때, "이 장을 어떤 레이아웃으로 잡지" 를 판단할 때 사용함. PPTX 산출물의 좌표·폰트·색을 정하는 모든 작업이 대상.
---

# 결과보고 PPTX 디자인 시스템

레퍼런스 4개 덱 265슬라이드를 PPTX XML 에서 직접 실측해 만든 재현 규격임.
**추측하지 말고 이 문서의 수치를 쓸 것.** 여기 없는 값이 필요하면
"레퍼런스에 없음"으로 처리하고 사람에게 물을 것.

## 먼저 읽을 것

전체 규격은 `reference/design-system.md` 에 있음. 아래는 매번 지켜야 하는
핵심만 추린 것이고, 좌표·표·차트 사양을 실제로 쓸 때는 반드시 그 파일을 열 것.

## 절대 규칙 (위반 시 산출물 폐기)

1. **SAMSUNG SS 7종만.** Head KR Light/Regular/Medium/Bold + Body KR Light/Regular/Bold.
   `Samsung SS Body KR Medium` 은 **존재하지 않음** — 지정하면 다른 서체로 샘.
2. **bold 플래그 금지.** 웨이트는 패밀리명으로만 고름. python-pptx 에서는
   `rPr` 의 `b`/`i` 속성을 제거하고 `latin`·`ea`·`cs` 세 typeface 를 동일하게 기록.
   → `Scripts/utils/report/theme.py` 의 `set_run_font()` 가 이미 구현함. 그것만 쓸 것.
3. **원본 행을 지우지 말 것.** 표가 넘치면 행 높이를 낮춤
   (0.40 → 0.37 → 0.31 → 0.23 → 0.144 in). 삭제·요약은 CLAUDE.md 3.1 위반.
4. **레퍼런스에 없는 시각 언어를 만들지 말 것.** 그림자·글로우·베벨 0건,
   새 차트 유형 0건, 표 banding 0건. 필요하면 기존 표현을 변형할 것.

## 페이지 골격 (모든 콘텐츠 슬라이드 공통)

```
Canvas   13.333 × 7.5 in

y 0.30   캠페인 태그    x 0.49 · 16pt Head Medium · #000
                        "캠페인명 ｜ 페이지 기능명"  (기능명은 Head Regular)
y 0.69   헤더 괘선      x 0.55 · 1px · #000 · 폭은 태그 텍스트 hug
y 0.69   셰브런 플래그  x 0.55 · 0.22 × 0.23 in  + 라벨 x 0.70 · 16pt Head Medium
y 1.24   키메시지       중심 = 캔버스 중심 6.667 in
                        kicker 18pt Head Light → MAIN 24pt Head Bold → sub 18pt Light
                        ★ 전부 중앙 정렬 (68/72 슬라이드에서 확인)
y 2.56   콘텐츠 존      전폭 패널 x 0 · w 13.33 · #F8F9FD
y 7.02   각주          x 0.38 · 8pt Body Light · #7F7F7F · "*" 로 시작
```

타이포 비율 — 키메시지 24 : 본문 12 = **2.0 : 1**.
13·15·17·22pt 같은 중간 크기를 새로 만들지 말 것.

## 색 (전체 팔레트는 reference 파일)

```
#0096FF Primary(면적 5% 이내)   #E1F3FF 표 헤더(검정 글자)   #F8F9FD 패널
#000000 제목·태그               #404040 본문                #7F7F7F 각주
#FEF5BE 강조 셀(유일)           #767171 합계 행(합계 전용)   #D9D9D9 괘선
#F2F2F2 표 라벨열               #1457C9 결론 밴드           #D96D77 미달
```

강조 장치는 **페이지당 1종**. 크림 셀과 액센트 블루를 겹치지 말 것.

## 페이지를 만들 때의 판단 순서

1. 이 장이 독자의 어떤 질문에 답하는가 (콘텐츠·목적)
2. 정보 구조 — 단일 메시지 / 병렬 / 시계열 / 대조 / 정량 표
3. Content Archetype 지정 → A-01 ~ A-13 중 하나 (reference 파일 §9)
4. 의미적으로 가장 유사한 레퍼런스 페이지 검색
   (목적 25% · 정보구조 20% · 콘텐츠유형 15% · 시각위계 15% ·
    레이아웃 10% · 밀도 10% · 시각처리 5%)
5. 그 페이지의 좌표·그리드·여백·정렬을 **그대로** 계승
6. 텍스트·수치·이미지·항목 수만 변경. 항목 수 차이는 그리드로만 흡수

## 이 저장소에서의 구현 위치

| 대상 | 파일 |
|---|---|
| **토큰·컴포넌트·표·차트 헬퍼 (단일 출처)** | `Scripts/utils/report/theme.py` |
| 슬라이드 블록 레지스트리 (21블록) | `Scripts/utils/report/blocks.py` |
| 슬라이드별 렌더 | `Scripts/utils/report/renderer.py` |
| 화면 미리보기 (같은 좌표계) | `Scripts/utils/slide_preview.py` |
| cm 단위 어댑터 (상수 없음, theme 파생) | `Scripts/utils/report/design_spec.py` |
| 폰트 설치 확인 | `Scripts/utils/report/fonts.py` |

`theme.py` 의 상수·헬퍼가 이 디자인 시스템의 **단일 출처**임.
**슬라이드 코드에 좌표·색·폰트를 직접 쓰지 말고 `theme.py` 를 경유할 것.**
새 값이 필요하면 `theme.py` 에 상수로 올린 뒤 쓸 것.

`design_spec.py` 는 cm 단위를 쓰는 호출부(`test_ppt_render.py`)를 위한
어댑터일 뿐이며 자체 상수를 갖지 않음 — 여기에 값을 새로 적지 말 것.

## 검증

산출물을 낸 뒤 아래를 돌릴 것.

```bash
python Scripts/test_design_compliance.py && python Scripts/test_ppt_render.py && python Scripts/test_layout_overlap.py && python Scripts/test_text_safety.py && python Scripts/test_render_sim.py
```

**`test_design_compliance.py` 가 이 문서의 준수 여부를 기계로 판정한다.**
산출물 PPTX 를 열어 캔버스·폰트·크기·색·헤더 3단·키메시지·전폭 패널·각주·
표 헤더/합계/행높이를 좌표 단위로 대조하고 준수율을 낸다. 규격을 바꾸면
이 검사도 함께 고칠 것 — 안 그러면 문서와 코드가 조용히 갈라진다.
"디자인 시스템을 적용했다"는 주장은 이 검사 통과로만 확인할 것.

출고 전 사람이 볼 항목은 `reference/design-system.md` §12 QA 체크리스트.

## 출처 표기

모든 수치는 아래 3단계로 구분해 말할 것.

- **CONFIRMED** — PPTX XML 에서 직접 읽은 값
- **ESTIMATED** — 렌더 이미지에서 육안 계측한 값
- **INFERRED** — 복수 페이지 패턴에서 도출한 규칙

불확실한 값을 사실처럼 쓰지 말 것.
