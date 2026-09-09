# 작업 인수인계 — AFTER CAMPAIGN (2026.09.09)

> 다른 세션/계정에서 이어서 작업할 때 이 파일 전체를 첫 메시지로 붙여 넣을 것.
> 저장소: https://github.com/finklkdi-art/AFTER-CAMPAIGN · 브랜치 `main`
> 로컬 경로: `C:\Users\CHEIL\Desktop\AX3BB`

---

## 0. 지금 상태 한 줄

레퍼런스 4개 덱에서 실측한 디자인 시스템을 산출물 PPTX 와 웹 화면에 적용했고,
준수 검사 100 % 통과 상태로 `origin/main` 에 푸시까지 끝났음.
**단, Streamlit Cloud 앱은 아직 Reboot 하지 않아 배포 반영 전임.**

---

## 1. 가장 먼저 할 일

1. **Streamlit Cloud 앱 대시보드에서 Reboot.**
   `theme.py` · `step2_macro.py` · `blocks.py` · `theme_css.py` 는 전부 import
   모듈이라 푸시만으로는 안 바뀜. 또 `requirements.txt` 의 streamlit 최소
   버전을 `>=1.37` 로 올렸는데(st.dialog 요구), 의존성 재설치도 재기동 때 일어남.
   **배포 환경 streamlit 이 1.37 미만이면 기본 정보 팝업이 AttributeError 로 죽음.**
2. Reboot 후 확인할 것 — ① 2단계 진입 시 팝업이 뜨는가 ② 입력 순서가
   광고주 → 제품명 → 캠페인명 → 작성일자 인가 ③ 받은 PPTX 표지에
   `캠페인명 / 결과보고서 / 작성일자` 가 찍히는가.

---

## 2. 이번 세션에 올린 커밋 (모두 origin/main 반영 완료)

```
d9bf9c7  feat(ui)      기본 정보 팝업(st.dialog) + 표지 표기 개편
0d84114  feat(design)  표지·간지·차트·표를 레퍼런스 아키타입으로 재구성
ff490da  test(design)  디자인 시스템 준수 검사 도입 + 미준수 4건 교정 (78%→100%)
a5c11c5  fix(report)   기간 파싱 크래시 · DRM 잠김 표면화 · 본문에 디자인 적용
ba1de75  refactor      design_spec 을 theme.py 어댑터로 전환 (규격 단일 출처화)
5725d94  feat(design)  결과보고 PPTX 를 실측 디자인 시스템에 정렬 + 스킬로 고정
e1560ca  refactor      매체 차트를 계획 대비 비교에서 실집행 지표 비교로 전환
```

---

## 3. 만들어 둔 자산

| 자산 | 위치 | 비고 |
|---|---|---|
| 디자인 시스템 스킬 | `.claude/skills/report-design-system/` | 리포트 작업 시 자동 로드 |
| 규격 원문 | `.claude/skills/report-design-system/reference/design-system.md` | 스킬 안에 복제 (자족적) |
| 준수 검사 | `Scripts/test_design_compliance.py` | 인자 없이 실행하면 덱을 직접 만들어 검사 |
| 디자인 캔버스(아트보드 10장) | https://claude.ai/code/artifact/2dc4cc30-a44b-4237-bed2-41ad277e41aa | 실측 근거·페이지 계보 |
| 캔버스 원본 파일 | `Output/DesignSystem/*.dc.html` | **gitignore 됨 — 저장소에 없음** |

> `Output/` 은 통째로 gitignore 라 캔버스 원본은 이 PC 에만 있음.
> 규격 자체는 스킬 안 `reference/design-system.md` 에 복제해 뒀으므로,
> 다른 PC 에서는 그 파일과 위 아티팩트 링크를 근거로 쓰면 됨.

---

## 4. 디자인 시스템 핵심 (자세한 건 스킬 참조)

레퍼런스 4개 덱 265슬라이드를 PPTX XML 에서 직접 실측한 규격.
**`Scripts/utils/report/theme.py` 가 단일 출처**이며, 슬라이드 코드에
좌표·색·폰트를 직접 쓰지 말고 반드시 theme 을 경유할 것.

```
폰트   SAMSUNG SS 7종만 (Head KR Light/Regular/Medium/Bold + Body KR Light/Regular/Bold)
       Body KR Medium 은 존재하지 않음. bold 플래그 금지 — 웨이트는 패밀리명으로.
골격   태그 0.49/0.30 → 괘선 0.55/0.69 → 셰브런 0.55/0.77 + 라벨 0.70/0.75
       키메시지 0.99/1.24 (중심 6.667 = 캔버스 중심) 24pt Head Bold 중앙
       콘텐츠 패널 y 2.56 전폭 · 각주 y 7.02 8pt Body Light
색     #0096FF Primary(면적 5% 이내) · #E1F3FF 표헤더 · #F8F9FD 패널
       #FEF5BE 강조셀 · #767171 합계행 · #404040 본문 · #7F7F7F 각주
표     행 넘치면 지우지 말고 높이 낮춤 (0.403→0.37→0.311→0.234→0.144)
       theme.row_height_for() 사용. 결측 셀은 45° 사선 해칭.
```

---

## 5. 남은 작업 (우선순위 순)

1. **결론 밴드 · KPI 타일 연결** — `theme.add_conclusion_band` /
   `add_kpi_tile` 이 만들어져 있으나 아무도 호출하지 않음.
   `_slide_insight` · `_slide_strategy` · `_slide_kpi` 가 밀도에 따라 배치를
   다시 계산하는 **적응형 레이아웃**이라, 붙이려면 그 장들의 배치 로직을
   새로 짜야 함. 잘 도는 폴백이 깨질 위험이 있어 손대지 않고 남겨 둠.
2. **`_slide_quotes` 키메시지 없음** — 콘텐츠 장인데 키메시지가 빠져 그 장만
   위계가 끊김. payload 키를 확인한 뒤 붙일 것.
3. **카드 시스템(C-04)** — radius 19pt / 패딩 0.24in / 내부 5단 순서.
   `_slide_creative_cards` · `_slide_placement_cards` 에 미적용.
4. **실제 캠페인 데이터로 표·KPI 장 검증** — DRM 해제 후 확인 필요 (아래 참조).

---

## 6. 반드시 알아야 할 함정 4가지

### ① Streamlit 모듈 캐시
import 모듈은 푸시·파일 저장만으로 반영되지 않음. 로컬은 서버 재시작,
배포는 Reboot 필요. 이번 세션에서 이것 때문에 "고쳤는데 옛날 에러가 계속
뜨는" 상황을 한 번 겪음.

### ② 사내 DRM (NASCA)
`Input/Samples/` 의 캠페인 파일이 **주기적으로 다시 잠김**. 헤더가
`<## NASCA DRM FILE` 이면 잠긴 것. 잠기면 21블록 중 16개가 아무것도 만들지
못해 보고서가 placeholder 로만 채워짐 — **코드 버그로 오해하기 쉬움.**
확인: `head -c 8 <파일> | xxd`
또 **PowerPoint 가 쓰는 모든 출력물이 암호화**됨(슬라이드 PNG 내보내기 불가).
python 이 쓴 파일은 안 걸리므로, 산출물 검증은 python-pptx 로 좌표를 다시
읽거나 Pillow 로 재렌더링할 것. DRM 우회는 시도하지 않음(`utils/drm_check.py` 방침).

### ③ PPTX 생성 경로가 2개
- 운영: `blocks.py`(21블록) → `renderer.py` → `theme.py` ← 웹앱이 쓰는 경로
- 단독: `test_ppt_render.py` → `design_spec.py` → `theme.py`
`design_spec.py` 는 cm 단위 어댑터일 뿐 **자체 상수를 갖지 않음.**
규격은 `theme.py` 만 고칠 것. 눈으로 볼 때는 두 경로 다 확인.

### ④ Streamlit 위젯 key 중복
`st.dialog` 와 본문이 같은 key 를 쓰면 dialog 가 열려 있는 동안 둘 다 그려져
`StreamlitDuplicateElementKey` 로 **화면 전체가 죽음.** 팝업은 `*_dlg` 키로
자기 값을 들고 있다가 '확인' 때만 본문 키로 옮기는 구조로 되어 있음.

---

## 7. 검증 명령

```bash
python Scripts/test_design_compliance.py   # 디자인 규격 준수율 (현재 100%)
python Scripts/test_render_sim.py          # 실제 캠페인 렌더 26건
python Scripts/test_period_window.py
python Scripts/test_layout_overlap.py
python Scripts/test_text_safety.py
python Scripts/test_ppt_render.py
```

산출물을 눈으로 볼 때(운영 경로):
```python
run_step1(folder) → CampaignDatasetBuilder.build → ReportSpecBuilder.build
                  → ReportRenderer().render(spec, out)
```
DRM 때문에 PowerPoint 내보내기가 막히므로, 만든 PPTX 는 python-pptx 로
좌표를 다시 읽어 검증할 것.

---

## 8. 프로젝트 규칙 (CLAUDE.md 요약 — 위반 시 산출물 폐기)

- **원본 행·문서를 지우지 말 것.** 못 지키면 Checklist 에 기재 (3.1)
- 파싱 에러로 강제 종료 금지, AI 임의 판단·삭제 금지 (3.3)
- 교차 인용 시 `파일명:시트명` 출처 병기, 불일치는 양쪽 제시 (3.2)
- AE 가 확인하지 않은 항목은 확정 처리하지 말고 '미확인'으로 남길 것 (3.5)
- 화면 카피는 **해요체**, 접이식 박스로 본문 숨기지 말 것, 문장 중간 줄바꿈 금지 (5)
- 파일명 `YYMMDD_품목_자료명_v0_Cheil`
- 절대경로를 데이터에 저장하지 말 것

---

## 9. 첫 메시지 예시

> 위 HANDOFF.md 를 붙여 넣은 뒤 이어서:
>
> "인수인계 내용 확인했어. Streamlit Cloud Reboot 는 내가 했고,
>  이제 [남은 작업 1번 / 2번 / …] 을 진행해줘."
