# 배포 아키텍처 전환 — 작업 히스토리 (2026.09, 재개용)

무료 외부 호스팅 + URL 배포 / 인증 없음 / 세션 격리 + 완전 휘발성 전환.

## 이번 세션에서 완료한 것

### 문서 개정
- `claude.md` 1장 전면 개정 — 1.0 외부 API·호스팅 허용, 1.1 인증 없음,
  1.2 세션 격리+휘발성(핵심 방어), 1.3 잔여 리스크, 1.4 공통, 1.5 API 운영 관행.
  (구 '외부 전송 금지 / 100% 로컬 / Claude API 만 예외' 프레임 폐기)
- `Project_Rule_Book_v0.md` 1.1 v3.0 개정 + 1.1-A(휘발성) 신설, 1.4 예외조항 폐기 배너.

### 코드
- `Scripts/utils/report/revise.py` `load_api_key()` — 환경변수 → **st.secrets** → .env
  순으로 확장. streamlit 미컨텍스트에서도 try/except 로 안전 폴백. `api_available()` 문구 갱신.
- `.streamlit/config.toml` — localhost 바인딩 제거, headless/XSRF/maxUploadSize(50MB),
  showErrorDetails=false(경로·데이터 유출 방지), gatherUsageStats=false 유지.
- `.streamlit/secrets.toml.example` 신설 — 키 템플릿(ANTHROPIC/GEMINI).
- `.gitignore` — `secrets.toml`, `Output/Temp/`, `Input/Samples/`, 샘플 산출물 추가.
- `Config/web_deploy.json` — TTL 60→**30분**, `purge_uploads_after_report:true` 신설,
  `link_input_folder:false`(호스팅엔 서버 폴더 없음).
- `web_main.py` — 헤더 주석 개정, `purge_uploads(root)` 함수 신설, 3단계 진입 시 호출.
  (기존 세션 격리 uuid4·TTL 스윕·PPTX purge·destroy_session 는 이미 견고 → 유지)

### 검증
- 전 모듈 컴파일 OK, load_api_key 예외 없이 동작, config 로딩 OK.
- 서버 재기동 후 대문 정상 렌더 확인 (localhost:8502).

## 배포 방법 (Streamlit Community Cloud)
1. GitHub 레포 푸시 (`.gitignore` 로 secrets·Input/Samples·Output/Temp 제외 확인).
2. share.streamlit.io → New app → 메인 모듈 `web_main.py` 지정.
3. Settings > Secrets 에 `secrets.toml.example` 내용 붙여넣고 실제 키 입력.
4. requirements.txt 는 이미 존재 (anthropic 포함).

## 남은 작업 (다음 세션 후보)
- [ ] **requirements.txt 점검** — pypdfium2, python-pptx, pdfplumber, openpyxl,
      python-docx 등 호스팅 빌드에 필요한 전 의존성이 고정 버전으로 있는지 확인.
      (특히 pypdfium2 는 게재보고 PDF 렌더에 필수)
- [ ] **PPTX를 완전 BytesIO 경로로** — 현재는 디스크에 썼다가 즉시 purge(잔존 사실상 0).
      순수 인메모리로 바꾸려면 renderer.render() 에 BytesIO 반환 오버로드 추가 필요.
- [ ] **Gemini 키 실제 사용처 연결** — 이미지 생성 기능(디자인 단계 논의)을 붙일 때
      `GEMINI_API_KEY` 를 load 하는 어댑터 추가 (revise.load_api_key 패턴 재사용).
- [ ] 무료 서버 콜드스타트·메모리 한계(1GB) 실측 — 대용량 PPTX 업로드 시 OOM 여부.
- [ ] `app.py`(로컬 단독 진입점) 는 그대로 두되, 문서에서 '로컬 전용'→'로컬 확인용'으로 정리.

## 미해결 판단 이슈 (운영자 결정 필요)
- 클라이언트(삼성) 민감 자산이 **공개 호스팅 + 외부 API** 를 경유. 세션격리·휘발성은
  서버 잔존만 없앰. 공개 배포 전 컴플라이언스 확인 권장. (claude.md 1.3 에 기록)
