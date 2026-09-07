# Stage 3 인사이트 엔진 재설계 — 아키텍처 설계안

> 목표: Lesson Learned를 **데이터 요약**에서 **수석 AE의 기획적 해석**으로 끌어올린다.
> 근거 문서: [LESSON_LEARNED.md](LESSON_LEARNED.md) (실제 보고서 7장표 분석)
> 상위 규칙: [CLAUDE.md](CLAUDE.md) — 데이터 보존, 외부 전송 최소화, API 실패 시 강등, 근거·출처 병기.

---

## 0. 현황 진단 — 먼저 고쳐야 할 것

코드를 읽고 확인한 세 가지다. **F1이 품질 미달의 직접 원인이다.**

### F1. 🔴 Lesson 슬라이드가 인사이트 엔진을 쓰지 않는다
`utils/report/blocks.py:1584 _lesson()`은 `InsightSet`을 참조하지 않는다.

```python
if dataset.postbuy and dataset.postbuy.lesson_learned:   # ① 포스트바이 원문 복사
    ...
else:
    gap = dataset.gap('lesson_learned')                   # ② AE 직접 입력
```

즉 현재 산출물의 Lesson Learned는 **포스트바이 원문을 그대로 옮겨 적거나, AE가 타이핑한 것**이다.
`InsightEngine`이 만든 `InsightSet`(발견/제안/근거)은 **산출물에 도달하지 않는다.**
→ 엔진을 아무리 고도화해도 F1을 고치지 않으면 화면·PPT는 그대로다. **1순위 수정 지점.**

### F2. 🟠 A축(전략/메시지)의 데이터 원천이 비어 있다
`CampaignKnowledge.proposal.metadata`에 `campaign_goal` / `target_audience` /
`strategy_details` 필드는 **선언만 되어 있고 어떤 파서도 채우지 않는다**(전 코드 grep 확인).
→ "제안서의 기획 의도 vs 시장 반응" 대조는 **재료부터 만들어야 한다.** (§6에서 3안 제시)

### F3. 🟢 D·E축 데이터는 이미 파싱되어 있다
`MediaPerformance.axis`가 이미 `media / product / targeting / creative / purpose`를 지원한다.
소재별·목적(퍼널)별 실적 행이 **이미 들어와 있는데 이를 읽는 규칙 모듈만 없다.**
→ D축(크리에이티브)·E축(전환/퍼널)은 **파서 수정 없이 규칙 추가만으로** 가능. 가성비 최고.

---

## 1. 목표 파이프라인

```
 CampaignKnowledge(의도)  CampaignDataset(사실)  lesson_playbook.json(지식)
            └───────────────┬───────────────┘
                            ▼
   [1] intent.py      의도 vs 결과 1:1 대조 매트릭스 생성      (로컬)
                            ▼
   [2] rules_*.py     5축 규칙 → InsightCandidate[]            (로컬)
                            ▼
   [3] playbook.py    6패턴 매칭 → '기획적 해석(맥락)' 부여     (로컬)
                            ▼
   [4] composer.py    3단 논법 조립 → Insight[]  ★API 없이 완성 (로컬)
                            ▼
   [5] llm.py         (선택) Claude API로 문장 고도화           (외부·AE 확인)
                            ▼
   [6] Stage 1.5 [인사이트·레슨런 검증 탭] — AE 편집 → [승인]   ★게이트
                            ▼
   [7] blocks._lesson  InsightSet 소비 → PPTX 렌더              (F1 수정)
```

**핵심 원칙**: [4]까지로 문장이 **완성**된다. [5]는 품질 향상이지 필수 경로가 아니다.
API 키가 없거나 실패해도 [4] 결과가 그대로 [6]으로 간다 (CLAUDE.md 1.2 강등 원칙).

---

## 2. 모듈 구조 (`Scripts/utils/insight/`)

| 파일 | 상태 | 역할 |
|---|---|---|
| `axes.py` | ★신규 | 5축 상수·라벨·우선순위 정의 |
| `intent.py` | ★신규 | 의도(Plan/Proposal) ↔ 결과(Actual) 대조 매트릭스 |
| `playbook.py` | ★신규 | `Config/lesson_playbook.json` 로딩·조건 매칭 |
| `composer.py` | ★신규 | 3단 논법 문장 조립 (phrasing.py 활용) |
| `llm.py` | ★신규 | Claude API 초안 고도화 (revise.py 패턴 재사용) |
| `rules_message.py` | ★신규 | **A축** 전략/메시지 |
| `rules_creative.py` | ★신규 | **D축** 크리에이티브 (axis='creative' 소비) |
| `rules_funnel.py` | ★신규 | **E축** 전환/퍼널 (axis='purpose' + KpiTarget + analytics) |
| `rules_media.py` | 수정 | **B축**으로 재정의 (예산 비중 vs 효율) |
| `rules_targeting.py` | 수정 | **C축** 유지 + 의도 대조 결합 |
| `rules_kpi.py` `rules_period.py` | 유지 | B·E축 보조 신호로 흡수 |
| `engine.py` | 개편 | 위 흐름 오케스트레이션 |
| `phrasing.py` `metrics.py` `config.py` | 유지 | 그대로 재사용 (명사형 종결·조사·수치 표기 이미 완비) |

### 데이터 모델 확장 (`models/campaign_data.py`)
기존 `Insight`를 **확장**한다(신규 dataclass 대신 — 호환 유지).

```python
@dataclass
class Insight:
    axis: str = ""              # 'A'|'B'|'C'|'D'|'E'  (기존 media/targeting/... 대체)
    finding: str = ""           # 1단 발견(Fact)
    context: str = ""           # ★신규 2단 평가(Context)
    recommendation: str = ""    # 3단 제언(Action)
    evidence: List[str] = ...
    sources: List[str] = ...
    priority: float = 0.0
    metrics: Dict[str, Any] = ...
    # ── 신규 ──
    pattern: str = ""           # 'P1'~'P6'
    intent: str = ""            # 대조된 '원래 의도' 문장
    confidence: str = "medium"  # high|medium|low
    origin: str = "rule"        # rule|api|ae
    block_id: str = ""          # 부분 리렌더링 단위
    approved: bool = False      # AE 승인 여부
```

---

## 3. 5축 정의와 데이터 매핑

| 축 | 이름 | Intent 원천 | Fact 원천 | 가용성 |
|---|---|---|---|---|
| **A** | 전략/메시지 | `proposal` 핵심메시지·목표 | postbuy `search`/`buzz` 섹션, CTR | 🔴 **의도 추출 필요** |
| **B** | 매체/상품 효율 | `PlanLine.budget` / `expected_*` | `MediaPerformance(axis=media·product)` | 🟢 가용 |
| **C** | 타겟팅 | `PlanLine.targeting` | `MediaPerformance(axis=targeting)` | 🟢 가용 |
| **D** | 크리에이티브 | `PlanLine.creative` | `MediaPerformance(axis=creative)` | 🟢 **가용(미사용)** |
| **E** | 전환/퍼널 | `PlanLine.purpose`, `KpiTarget` | `MediaPerformance(axis=purpose)`, analytics 섹션 | 🟢 **가용(미사용)** |

### `intent.py` — 대조 매트릭스
```python
@dataclass
class IntentFact:
    axis: str            # A~E
    key: str             # 대조 키 (매체명·타겟라인·소재명·purpose)
    intent_label: str    # "계획 예산 비중 32%" / "관심사 타겟팅 중심"
    intent_value: Optional[float]
    fact_label: str      # "실집행 비중 28%, VTR 57.6%"
    fact_value: Optional[float]
    delta: Optional[float]      # 의도 대비 증감 (비율)
    verdict: str         # 'exceeded'|'met'|'short'|'shifted'|'absent'
    sources: List[str]

def build(knowledge, dataset) -> List[IntentFact]: ...
```
→ 모든 규칙은 `IntentFact`를 입력으로 받는다. **"의도 대비 결과가 어떠했는가"가 구조적으로 강제**된다.

---

## 4. Playbook — 기획적 해석의 자산화

### `Config/lesson_playbook.json`
```jsonc
{
  "version": 1,
  "patterns": {
    "P1": { "name": "성과-한계형", "shape": "{A}는 유효했으나 {B} 부족 → {C} 필요" },
    "P2": { "name": "성과-확대형", "shape": "{A} 달성·기여 → {B}로 확장" },
    "P3": { "name": "부재-보완형", "shape": "{A} 부재 → {B} 마련 필요" },
    "P4": { "name": "실험-정착형", "shape": "{A} 테스트 → 지속 확보" },
    "P5": { "name": "운영노하우형", "shape": "{A} 운영 → 다음엔 {B} 권장" },
    "P6": { "name": "편중-확장형", "shape": "{A} 집중 → {B}로 커버리지 확대" }
  },
  "entries": [
    {
      "id": "targeting_keyword_over_interest",
      "axis": "C", "pattern": "P2",
      "when": { "compare": "targeting", "metric": "vtr", "winner_contains": ["키워드", "검색"], "min_gap_pp": 3 },
      "context": "관심사 위주 노출보다 명확한 실수요(검색) 기반 타겟팅의 유효성 입증",
      "action": "차기 캠페인 시 {winner} 라인 예산 비중 {suggest_share} 이상 상향 편성 권장",
      "confidence": "high",
      "seed_from": "OLED TV 25 / 시스템에어컨 25"
    },
    {
      "id": "creative_single_fatigue",
      "axis": "D", "pattern": "P5",
      "when": { "creative_count": 1, "period_days_gte": 30 },
      "context": "단일 소재 장기 운영 시 노출 피로도 누적 가능성",
      "action": "캠페인 중반 이후 소재 교체 또는 멀티 소재 병행 운영 권장",
      "confidence": "medium",
      "seed_from": "무빙스타일 25"
    }
  ]
}
```

- `when`은 **로컬에서 판정 가능한 조건만** 둔다(외부 호출 없음).
- `context`가 바로 **3단 논법의 2단(평가)** 이다. 수치는 규칙이, 해석은 playbook이 댄다.
- **시드**: 이번 분석 7장표에서 뽑은 문장을 v1로 넣는다(§6-3 확인 필요).
- 캠페인 종료 시 AE가 한 줄씩 추가 → 사내 지식이 누적된다.

---

## 5. Claude API 프롬프트 설계 (`insight/llm.py`)

`utils/report/revise.py`의 검증된 패턴을 그대로 따른다 —
`load_api_key` → `api_available` → 전송 payload 화면 노출 → **AE 실행 확인** → 실패 시 `degrade`.

### 5.1 최소 전송 (CLAUDE.md 1.2 준수)
**원본 문서·전체 데이터셋을 절대 보내지 않는다.** 규칙이 만든 **구조화 슬롯만** 보낸다.

```python
payload = {
  "campaign": {"name": ..., "category": ..., "period": ...},   # 식별 최소
  "candidates": [
    {"axis": "C", "pattern": "P2",
     "intent": "제안서: 관심사 타겟팅 중심 운영",
     "facts": ["유튜브 키워드 타겟팅 VTR 57.6%", "관심사 타겟팅 VTR 52.6%", "격차 5.0%p"],
     "playbook_context": "명확한 실수요(검색) 기반 타겟팅의 유효성",
     "draft": {"finding": "...", "context": "...", "action": "..."}}
  ]
}
```

### 5.2 SYSTEM_PROMPT (핵심)
```text
당신은 광고대행사의 수석 AE다. 캠페인 결과보고서의 'Lesson Learned' 문장을 다듬는다.

[역할]
데이터 요약이 아니라 '기획적 해석'을 쓴다. 숫자가 무엇을 의미하는지, 다음에 무엇을
바꿔야 하는지까지 적는다.

[3단 논법 — 반드시 이 구조]
1. finding(발견): 수치 기반 팩트. 매체·상품·소재·타겟 라인명과 지표를 반드시 인용.
2. context(평가): 그 수치가 기획적으로 무엇을 뜻하는지 해석. 원래 의도(intent)와 대조.
3. action(제언): 차기 캠페인에서 실행 가능한 구체 액션. 대상·방향·정도를 명시.
   (나쁜 예: "타겟팅 개선 필요" / 좋은 예: "유튜브 키워드 라인 예산 비중 30% 이상 상향 편성 권장")

[문체 — 위반 시 불합격]
- 개조식 명사형 종결만 사용: ~기록 / ~달성 / ~확보 / ~입증 / ~권장 / ~필요 / ~제언
- 서술형 어미 금지: ~했습니다 / ~입니다 / ~한다 / ~이다
- 숫자를 먼저, 해석을 뒤에.
- 한 문장 45자 이내. finding·context·action 각 1~2문장.

[사실 규칙 — 가장 중요]
- 입력 facts에 없는 수치·매체명·소재명을 새로 만들지 마라. 추론된 값도 쓰지 마라.
- facts가 비어 있으면 그 후보는 생성하지 말고 skip: true 로 반환하라.
- 데이터 없는 긍정 포장을 금지한다. 과장 수식어(획기적, 압도적)를 쓰지 마라.
- 경쟁사는 'X사', 자사는 '당사'로 표기한다.

[출력]
JSON 배열만 반환. 설명 문장 금지.
[{"id": <입력 id>, "finding": "...", "context": "...", "action": "...", "skip": false}]
```

### 5.3 호출 파라미터
`MODEL='claude-opus-5'`, `output_config={'effort':'low'}`(revise.py와 동일 — 문안 다듬기),
`max_tokens` 여유. 실패·키 없음 → **[4] 규칙 문장을 그대로 사용**하고 Checklist에 사유 기재.

### 5.4 검증 게이트 (환각 차단)
API 응답을 그대로 믿지 않는다. `llm.py`가 후처리 검증한다.
1. `finding`에 등장한 **수치가 입력 facts에 존재하는지** 문자열 대조 → 없으면 규칙 문장으로 롤백
2. 서술형 어미(`습니다|입니다|한다|이다`) 정규식 검출 → 검출 시 롤백
3. `action`이 20자 미만이거나 동사 없는 상투구면 롤백
→ 롤백 건수는 Checklist에 기재.

---

## 6. AE 검증·승인 동선 (Stage 1.5)

### 6.1 새 탭 — `dashboard/step2_insight.py`
Stage 1.5 대시보드에 **[인사이트 및 레슨런 검증]** 탭 추가.

- 축(A~E) 태그 + 패턴(P1~P6) 배지
- 항목마다 **3개 텍스트 박스**(발견 / 평가 / 제언) — 직접 편집
- 우측에 **근거·출처·의도** 읽기 전용 표시 (수정 시 근거가 안 보이면 검증이 안 됨)
- 항목별 [제외] 토글, [AI로 다듬기] 버튼(전송 payload 미리보기 + 실행 확인)
- 하단 **[인사이트 승인]** 단일 버튼

### 6.2 파이프라인 게이트
```python
# dashboard/state.py
KEY_INSIGHT_SET = 'ax_insight_set'
KEY_INSIGHT_APPROVED = 'ax_insight_approved'   # False 면 Stage 4 진입 차단
```
- `step3_generate`의 생성 버튼은 `KEY_INSIGHT_APPROVED`가 True일 때만 활성.
- 미승인 상태로 진입 시 `T.note('인사이트 검증을 먼저 마쳐 주세요.', 'warn')`.
- **승인 없이 통과한 항목은 없다** — 승인 자체가 Checklist에 기록된다.

### 6.3 Checklist 기재 (CLAUDE.md 3.4)
- 자동 도출 N건 / AE 수정 M건 / 제외 K건
- API 사용 건수 + 검증 롤백 건수
- 축별 도출 실패 사유 (예: A축 의도 미입력으로 생성 불가)

### 6.4 부분 리렌더링 연결
`Insight.block_id = f'lesson-{axis}-{idx}'` 를 부여하고 `ReportSpec` 블록 레지스트리에 등록.
→ Stage 4.5 미리보기에서 **카드 한 장만** 다시 만들 수 있다(파싱 재실행 없음).

---

## 7. F1 수정 — 산출물 연결

`blocks._lesson()`의 우선순위를 뒤집는다.

```python
# 1순위: 승인된 InsightSet (엔진 산출)
# 2순위: AE 직접 입력 gap
# 3순위: postbuy 원문  ← 폴백으로 강등
```
포스트바이 원문(`postbuy.lesson_learned`)은 **버리지 않는다.** 두 용도로 보존한다.
1. `intent.py`의 **대조군**(전 캠페인의 학습)
2. Playbook 후보 시드
3. 원문 자체는 Appendix 또는 Checklist에 보존 (데이터 보존 원칙 3.1)

---

## 8. 안전장치 요약

| 위험 | 대응 |
|---|---|
| API 키 없음/실패 | [4] 규칙 문장으로 강등, 전 기능 동작 |
| 환각(없는 수치 생성) | §5.4 3중 검증 후 롤백 |
| 과다 전송 | 구조화 슬롯만 전송, 원본 문서 금지, 전송 전 화면 노출 + AE 확인 |
| 근거 없는 문장 | `evidence` 비면 채택 안 함 (기존 engine.py 규칙 유지) |
| 조용한 소실 | 제외 사유 전량 `InsightSet.excluded` → Checklist |
| AE 미확인 통과 | 승인 게이트 + Checklist '미확인' 기재 |

---

## 9. 구현 순서 (권장)

| 단계 | 내용 | 효과 |
|---|---|---|
| **1** | **F1 수정** — `_lesson()`이 InsightSet 소비 | 엔진 산출물이 비로소 산출물에 도달 |
| **2** | `axes.py` + `Insight` 확장 + `composer.py` (3단 논법) | 문장 구조가 실제 보고서와 일치 |
| **3** | `rules_creative.py` `rules_funnel.py` (D·E축) | 파서 수정 없이 축 2개 확보 |
| **4** | `intent.py` + B·C축 의도 대조 결합 | "의도 vs 결과" 구조 강제 |
| **5** | `playbook.py` + 시드 JSON | 기획적 해석(맥락) 부여 |
| **6** | `step2_insight.py` + 승인 게이트 | AE 교정 동선 |
| **7** | `llm.py` (API 고도화 + 검증) | 문장 품질 마감 |
| **8** | A축 의도 입력 + `rules_message.py` | 가장 중요하나 재료 확보가 선행 |

1~3단계만으로도 현재 대비 체감 품질이 크게 오른다(F1 + 3단 논법 + 축 2개 추가).

---

## 10. 확인이 필요한 것 · 제안

### Q1. A축 '기획 의도'를 어떻게 확보할까 (F2)
현재 재료가 없다. 세 가지 안:

| 안 | 방법 | 장점 | 단점 |
|---|---|---|---|
| **(a)** | Stage 1.5에서 AE가 **핵심 메시지·목표 3줄 직접 입력** | 확실·즉시 가능·전송 없음 | AE 손이 감 |
| (b) | 제안서를 Claude API로 요약 추출 | 자동 | 전송량 큼 → 1.2 최소전송 원칙과 충돌 검토 필요 |
| (c) | 제안서 슬라이드 제목·키메시지 휴리스틱 추출 | 로컬·자동 | 정확도 낮음, 후보 수준 |

→ **추천: (c)로 후보를 뽑아 (a)에서 AE가 확정.** 이미 있는 `DataGap` 패턴과 동일한 UX다.
(b)는 옵션으로 두되 기본 비활성.

### Q2. 포스트바이 원문 Lesson Learned를 어떻게 다룰까
지금은 이걸 그대로 복사해 슬라이드로 만든다. 엔진 문장으로 대체하면 **원문이 산출물에서 사라진다.**
→ 제안: 산출물 본문은 엔진 문장, 원문은 Appendix 보존 + Checklist 기재. 괜찮을까?

### Q3. 슬라이드 분량 — 축당 몇 건?
현재 `max_insights` 기본 4건. 실제 보고서는 3~4쌍이 표준(§LESSON_LEARNED 분석).
→ 제안: **축당 최대 2건, 총 5~6건**, `_pack_lesson_pages`로 2장 분할. 조정할까?

### Q4. 승인 게이트 위치
Stage 1.5 탭에 넣으면 **인사이트 생성이 Stage 1.5보다 앞서야** 한다(현재는 Stage 3).
두 방법:
- **(가)** 인사이트 생성을 Stage 2 직후로 앞당기고 1.5에서 함께 검증 ← 동선 단순
- (나) Stage 3 뒤에 '3.5 검증' 단계 신설 ← 현 파이프라인 유지, 단계 하나 증가

→ 지시하신 대로라면 (가). 다만 Stage 1.5의 '거시 검증' 성격(뼈대 확정)과 섞이는데,
**탭으로 분리**하면 부담은 크지 않다고 봄. 어느 쪽으로 갈까?

### Q5. Playbook 초기 시드
이번 분석에서 뽑은 문장(키워드 타겟팅 유효성, 단일 소재 피로도, CTV 별도라인, 머신러닝 최적화,
멀티소재 예산 미구분, OOH 동선 연계 등)을 v1 엔트리로 넣을까?
→ 넣으면 첫 캠페인부터 해석이 붙는다. 다만 **삼성 가전 캠페인 맥락**이라 타 광고주엔 안 맞을 수 있어
`when` 조건에 `category` 스코프를 둘지 정해야 한다.
