# 광고 캠페인 결과 리포트 자동화 솔루션 — 작업 재개

프로젝트 경로: `C:\Users\CHEIL\desktop\ax3bb`
작업 시작 전에 반드시 `claude.md`(= CLAUDE.md)와 `Project_Rule_Book_v0.md`를 먼저 읽어라.
이 두 문서가 이 프로젝트의 실행 규칙이며, 아래 내용과 충돌하면 두 문서가 우선한다.

---

## 1. 지금까지 완료된 것 (재작업 금지 — 검증 완료 상태)

- **Stage 1** 파일 스캔 · 문서 역할 추론 (`Scripts/data_scanning.py`, `utils/role_classifier.py`)
- **Stage 1.5** Streamlit 검수 UI (`Scripts/stage_1_5_verification.py`, `app.py`)
- **Stage 2 · 4** 데이터셋 빌드 및 PPTX 생성 (`utils/dataset_builder.py`, `utils/report/`)
- **Stage 3 인사이트 엔진** `Scripts/utils/insight/`
  - 규칙 4축: 매체·상품 효율(`rules_media.py`) / 타겟팅(`rules_targeting.py`) /
    목표 달성률(`rules_kpi.py`) / 기간·Phase 추이(`rules_period.py`)
  - 산출물: Lesson Learned 슬라이드 + 차기 전략 슬라이드 (`strategy.py`, `phrasing.py`)
- **로드맵**: 매체별 + 소재별 2장, 기간 결손 보정 (`utils/roadmap_overlay.py`)
- **목적(purpose) 축**: 목적별 집행 결과 표
- **소재 이미지 카드**: `utils/creative_assets.py` (폴더 이미지 자동 매칭 + 자리표시자)
- **데이터셋 스냅샷 저장·복원**: `utils/dataclass_io.py`, `utils/dataset_snapshot.py`
  → STEP 1에 "이전 작업 이어하기" UI 연결됨
- **DRM 감지**: `utils/drm_check.py`를 파서 4개 진입점에 연결
- 샘플 6건 + 가상 광고주 1건 E2E 통과, 매체별 합계 = 캠페인 Total 차이 0원

---

## 2. 반드시 지킬 결정 사항 (코드만 봐서는 알 수 없는 합의 사항)

1. **매체 효율 최우수 선정에 집행 비중 하한을 두지 않는다.**
   `Config/insight_rules.json`에 `min_spend_share` 키가 없는 것은 의도된 설계다.
   대신 비중 5% 미만이면 제안 문구를 "테스트 물량 확대 후 본물량 편성 검토"로 낮춘다.
2. **Lesson Learned는 포스트바이 원문 우선.** 원문이 존재하면 자동 도출분은 슬라이드에
   싣지 않고, 차기 전략 슬라이드와 Checklist로만 반영한다.
3. **발견·제안·근거 3단은 전량 자동 생성.** 별도 검증 UI를 두지 않고 Checklist에
   "자동 도출 제안 N건 — 문구 검증 필요"를 남긴다.
4. **매체명은 데이터에 원본 보존.** 슬라이드 문장에서만 매체군 접두를 제거한다.
5. **자동 생성 문구 면책 각주는 PPT 1페이지 Checklist에만.** 광고주가 보는 본문에는 금지.
6. **파서 판정 키워드에 '관심'·'구매'를 넣지 말 것.** `MF3554∩관심사+구매의도` 같은
   타겟팅 표기에 걸려 타겟팅이 '목적'으로 오분류된다 (실측으로 확인된 사항).

---

## 3. 이번에 할 일

### 3-1. 통합 테스트

`Input/Samples`의 6개 캠페인 전부에 대해 Stage 1 → 2 → 3 → 4를 실행하고 슬라이드 생성을 확인한다.

대상 캠페인 (실측 폴더명):
- `(VD) 2025 OLED TV 캠페인`
- `(VD) 2025 무빙스타일 캠페인`
- `(냉장고) 2025 AI 하이브리드 키친핏 Max 캠페인`
- `(세탁건조기) 2025 워시타워 공략 캠페인`
- `(시스템에어컨) 2025 인피니트라인 필름 캠페인`
- `(에어컨) 2025 AI 무풍콤보 런칭 캠페인`

검증 포인트 (모두 통과해야 함):
- 매체별 Total 합 = 캠페인 Total → **차이 0원**
- 축 분리 정확도: `product` / `targeting` / `creative` / `purpose` 4축이 서로 섞이지 않을 것
- 소계·평균 행 혼입 **0건**
- PPTX 기하 넘침(텍스트 박스 오버플로·표 이탈) **0건**
- 허용 외 폰트 · bold 플래그 **0건**

주의: 이전 세션의 검증 스크립트는 세션 전용 임시 폴더에 있어 사라졌다.
필요하면 새로 작성하되, 산출물은 `Output/Temp` 또는 스크래치패드에 두고
프로젝트 루트를 오염시키지 말 것.

### 3-2. 로컬 웹 배포 테스트

```bash
streamlit run app.py
```

STEP 1 → 2 → 3 전 구간 동작을 확인한다.

확인 항목:
- 캠페인 폴더 선택 및 파싱 정상 동작
- 결손 데이터 입력 / 건너뛰기 플로우
- "이전 작업 이어하기" 스냅샷 복원
- PPTX 생성 및 내려받기
- Stage 3 도출 건수 · 제외 사유 표시
- `.streamlit/config.toml`의 **localhost 바인딩**과 **텔레메트리 차단** 설정 유지 여부
- 폰트 미설치 경고 동작 (`Fonts/` 폴더 7종:
  SamsungSSHeadKR Light/Regular/Medium/Bold, SamsungSSBodyKR Light/Regular/Bold)

---

## 4. 제약 (예외 없음)

- **외부 DB · 업로드 · 외부 저장 금지.** Streamlit은 localhost 바인딩만.
- **외부 호스팅(클라우드 배포) 금지.** 이 프로젝트에서 "배포"는 각 AE PC에서의
  로컬 구동을 뜻한다.
- 모든 파일 I/O는 `encoding='utf-8'` 명시, 줄바꿈은 **LF** 유지
- **기존 파일을 수정할 때는 변경 내용(diff)을 먼저 보여주고 승인을 받은 뒤 적용**
- **파일 삭제는 대상을 나열하고 승인을 받은 뒤 실행**
- 절대경로 하드코딩 금지, 브랜드·매체명 하드코딩 금지
- 판단이 갈리는 지점은 임의로 정하지 말고 **질문할 것**

---

## 5. 남은 개발 항목

없음. 런칭 후 항목(동료 AE 배포 · 피드백 수집)만 남았다.
`Examples/` 폴더는 NASCA DRM 암호화 상태이며 이번 작업에서는 무시한다.

## 6. 참고

이전 세션의 백업 폴더(`backup_before_apply/`, `backup_round2~4/`)와 검증 스크립트는
세션 전용 임시 폴더에 있어 새 세션에서는 접근할 수 없다.
**프로젝트 폴더 자체는 모든 변경이 적용된 최신 상태**이므로 그대로 이어서 작업하면 된다.

먼저 3-1 통합 테스트부터 시작하고, 결과를 보고한 뒤 3-2 웹 배포 테스트로 넘어가라.
