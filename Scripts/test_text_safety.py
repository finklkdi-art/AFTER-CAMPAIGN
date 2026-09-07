# -*- coding: utf-8 -*-
"""
화면 텍스트 안전장치 회귀 테스트

    python Scripts/test_text_safety.py

여기 있는 케이스는 전부 **실제 화면에서 깨진 적이 있는 것들**이다.
한 번 겪은 문제가 다시 나오지 않게 고정해 둔다.

배경
  · `strip_paths` — 엑셀 잠금 파일(`~$…xlsx`)을 열다 난 예외가 절대 경로째로
    화면에 흘렀다. 경로는 AE 에게 정보를 주지 않으면서 호스팅 서버의 디렉터리
    구조까지 드러낸다.
  · `safe_md`  — 그 경로 속 `_` 가 이탤릭으로, `$` 가 LaTeX 수식으로 해석되며
    문장이 기울어진 수학 기호 덩어리로 렌더됐다.
  · `josa`     — '데일리리포트을 못 읽었어요' 처럼 조사가 어긋나 있었다.

주의 — 과잉 무해화도 버그다
  경로를 지운다고 'A/B 테스트', '노출/클릭' 같은 평범한 표현까지 잘라내면
  안 되고, 마크다운을 escape 한다고 화면에 역슬래시가 비쳐도 안 된다.
  아래 '보존' 케이스가 그걸 지킨다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard.theme_css import josa, safe_md, strip_paths   # noqa: E402


# (입력, 결과에 반드시 들어 있어야 하는 문자열, 설명)
STRIP_PATH_CASES = [
    (r"[Errno 13] Permission denied: 'C:\Users\CHEIL\Desktop\AX3BB\Input"
     r"\Samples\(에어컨) 2025 AI 무풍콤보 런칭 캠페인\데일리리포트_25년.xlsx'",
     '데일리리포트_25년.xlsx', 'Windows 절대경로 → 파일명'),

    ('/home/adminuser/venv/app/Output/Temp/x.pptx 를 못 읽었어요',
     'x.pptx 를', 'POSIX 절대경로 → 파일명'),

    # ↓ 여기부터는 '건드리면 안 되는' 케이스
    ('계획 라인 19건 중 4건을 읽지 못했습니다. (정상) / 영향받는 슬라이드: 집행 로드맵',
     '/ 영향받는', "문장 구분자 ' / ' 보존"),

    ('A/B 테스트 결과 · 노출/클릭 비율',
     'A/B 테스트 결과 · 노출/클릭 비율', '슬래시 붙은 표현 보존'),

    ('자료원: 데일리리포트_25년 AI무풍콤보_런칭캠페인.xlsx <일자별 통합>',
     '자료원: 데일리리포트_25년 AI무풍콤보_런칭캠페인.xlsx', '경로 없는 파일명 보존'),

    ('경로 없는 평범한 문장이에요.', '경로 없는 평범한 문장이에요.', '평문 보존'),
]

# (입력, 결과에 나오면 안 되는 문자, 설명)
SAFE_MD_CASES = [
    ('데일리리포트_25년_AI무풍콤보.xlsx', '_', '언더스코어 이탤릭 방지'),
    ('금액 $1,000 과 $2,000', '$', 'LaTeX 수식 해석 방지'),
    ('*강조* 아닌 별표', '*', '별표 강조 방지'),
    ('~취소선~ 아님', '~', '물결 취소선 방지'),
]

JOSA_CASES = [
    ('데일리리포트', '을/를', '데일리리포트를'),
    ('제안 기간', '을/를', '제안 기간을'),
    ('포스트바이', '을/를', '포스트바이를'),
    ('소재', '이/가', '소재가'),
    ('믹스', '은/는', '믹스는'),
    ('서울', '으로/로', '서울로'),      # ㄹ 받침 예외
    ('보고서', '으로/로', '보고서로'),
    ('PDF', '을/를', 'PDF를'),          # 한글이 아닌 경우
]


def main() -> int:
    failed = []

    for src, must_contain, why in STRIP_PATH_CASES:
        out = strip_paths(src)
        if must_contain not in out:
            failed.append(f'strip_paths [{why}]\n    기대(포함): {must_contain}'
                          f'\n    실제      : {out}')

    for src, forbidden, why in SAFE_MD_CASES:
        out = safe_md(src)
        # escape 되었으므로 원문자는 반드시 역슬래시를 달고 나와야 한다
        bare = out.replace('\\' + forbidden, '')
        if forbidden in bare:
            failed.append(f'safe_md [{why}]\n    escape 안 된 {forbidden!r}: {out}')

    for word, pair, expected in JOSA_CASES:
        out = josa(word, pair)
        if out != expected:
            failed.append(f'josa [{word} + {pair}]\n    기대: {expected}'
                          f'\n    실제: {out}')

    total = len(STRIP_PATH_CASES) + len(SAFE_MD_CASES) + len(JOSA_CASES)
    if failed:
        print(f'실패 {len(failed)}건 / 전체 {total}건\n')
        for f in failed:
            print('  ' + f + '\n')
        return 1

    print(f'통과 {total}건 / 전체 {total}건')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
