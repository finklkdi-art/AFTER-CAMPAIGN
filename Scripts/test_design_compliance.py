# -*- coding: utf-8 -*-
"""
디자인 시스템 준수 검사 — 산출물 PPTX 가 실측 규격을 지키는가

    python Scripts/test_design_compliance.py            # 두 경로 모두 검사
    python Scripts/test_design_compliance.py <파일.pptx>  # 특정 덱만

"디자인 시스템을 만들어 적용했다는데 산출물이 그대로다"는 제보(2026.09.09)에서
출발했다. 사람 눈으로 "비슷해 보인다"를 판정하면 매번 결론이 달라지므로,
규격을 좌표·색·폰트 단위의 기계 검사로 고정한다.

측정 불가 항목(예: 표가 없는 덱의 표 규격)은 FAIL 이 아니라 SKIP 으로 센다 —
데이터가 없어서 못 지킨 것과 지키지 않은 것은 다르다.
"""
import sys, collections
from pptx import Presentation

EMU = 914400.0
ALLOWED = {
    'Samsung SS Head KR Bold', 'Samsung SS Head KR Medium',
    'Samsung SS Head KR Regular', 'Samsung SS Head KR Light',
    'Samsung SS Body KR Bold', 'Samsung SS Body KR Regular',
    'Samsung SS Body KR Light',
}
PALETTE = {
    '0096FF', '0070C0', '18A2FF', 'B3E0FF', 'E1F3FF', 'F8F9FD',
    '000000', '404040', '767171', '7F7F7F', 'D9D9D9', 'F2F2F2',
    'FEF5BE', '108BC6', '08ABBC', '0D9FC2', '1457C9', 'D96D77',
    'FFFFFF', '98D5FC', 'EDEDED', 'BFBFBF', '00C1B2', 'DDE7F2',
    # Structural — Color 시트의 보조색 행에 문서화된 값
    '3E86D6', 'EAF4FE', 'F1F6FC',
    # 차트 하단 구간 밴드 계조 (Data 시트 · 회색→청색)
    'D3DCE6', 'C1D0E0', 'AEC4DA', '9BB8D4',
    # 표지·간지 KV 그라디언트 (R03 P01 · R04 P02)
    '6B8FE0', '2C6FD0', '2C7BD6',
    # Checklist 전용 상태색 — 광고주 보고가 아니라 기획자 확인용이라 예외
    'A8761C', '1F6F4A',
}
LADDER = {0.403, 0.37, 0.311, 0.234, 0.144}

import os, io, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _build_sample() -> str:
    """운영 경로로 합성 캠페인 덱을 만들어 경로를 돌려준다."""
    from sim.fixtures import xlsx, docx, pptx as fx_pptx
    from utils.capture import capture_output
    from data_scanning import run_step1
    from utils.dataset_builder import CampaignDatasetBuilder
    from utils.report import ReportSpecBuilder, ReportRenderer

    tmp = pathlib.Path(tempfile.mkdtemp(prefix='dsaudit_'))
    camp = tmp / 'Camp'
    camp.mkdir()
    MEDIA = [['매체', '상품', '구분', '기간', '소재', '예산', '예상 노출']]
    for i, (m, prod) in enumerate((('유튜브', 'Trueview'), ('유튜브', 'Bumper'),
                                   ('META', 'Reels'), ('네이버GFA', 'SC'))):
        MEDIA.append([m, prod, '디지털', f'0{4+i//2}-01~0{5+i//2}-20',
                      f'소재{i}', 10_000_000 * (i + 1), 5_000_000 * (i + 1)])
    DAILY = [['일자', '매체', '노출', '조회', '클릭', '집행금액']]
    for i in range(30):
        DAILY.append([f'2025-04-{(i % 28) + 1:02d}', '유튜브',
                      100000 + i, 4000 + i, 90 + i, 160000 + i])
    (camp / '미디어 믹스_감사.xlsx').write_bytes(xlsx({'미디어믹스': MEDIA}))
    (camp / '데일리리포트_감사.xlsx').write_bytes(xlsx({'일자별 통합': DAILY}))
    (camp / '감사 Post-buy Report.pptx').write_bytes(fx_pptx([['KPI'], ['요약']]))
    (camp / '미디어 브리프_감사.docx').write_bytes(docx(['캠페인 목표']))

    out = tmp / 'audit.pptx'
    log = io.StringIO()
    with capture_output(log):
        k = run_step1(str(camp))
        d = CampaignDatasetBuilder.build(k)
        spec = ReportSpecBuilder.build(k, d)
        ReportRenderer().render(spec, str(out))
    return str(out)


TARGET = sys.argv[1] if len(sys.argv) > 1 else _build_sample()
SZ_OK = {36, 28, 24, 20, 18, 16, 14, 12, 11, 10, 10.5, 9, 8, 7}

prs = Presentation(TARGET)
W, H = prs.slide_width / EMU, prs.slide_height / EMU

def walk(shapes, out, d=0):
    for sh in shapes:
        st = str(sh.shape_type)
        rec = {'t': st, 'x': (sh.left or 0)/EMU, 'y': (sh.top or 0)/EMU,
               'w': (sh.width or 0)/EMU, 'h': (sh.height or 0)/EMU, 'sh': sh}
        if 'GROUP' in st:
            out.append(rec); walk(sh.shapes, out, d+1); continue
        out.append(rec)

results = []      # (id, 규격, 통과여부, 실측)
def chk(cid, spec, ok, got, skip=False):
    results.append((cid, spec, None if skip else bool(ok), got))

# ── 전역
chk('CANVAS', '13.333 × 7.5 in', abs(W-13.333) < .01 and abs(H-7.5) < .01,
    f'{W:.3f} × {H:.3f}')

fonts, sizes, colors, bolds = collections.Counter(), collections.Counter(), collections.Counter(), 0
fills = collections.Counter(); shadows = 0
panels = 0; tags = 0; rules = 0; chevrons = 0; labels = 0; keys = 0; foots = 0
tbl_head_ok = tbl_head_n = 0; tbl_total_ok = tbl_total_n = 0; rowh_ok = rowh_n = 0
content_slides = 0

for s in prs.slides:
    shapes = []
    walk(s.shapes, shapes)
    kinds = set()
    has_tag = has_rule = has_chev = has_lab = has_key = has_panel = has_foot = False
    for r in shapes:
        sh = r['sh']
        try:
            if ('AUTO_SHAPE' in r['t'] or 'PICTURE' in r['t']) and sh.shadow.inherit:
                shadows += 1
        except Exception:
            pass
        try:
            if 'SOLID' in str(sh.fill.type):
                fills[str(sh.fill.fore_color.rgb)] += 1
        except Exception:
            pass
        try:
            if 'CHEVRON' in str(sh.auto_shape_type):
                has_chev = True
        except Exception:
            pass
        if abs(r['x']) < .01 and abs(r['w']-13.333) < .02 and 2.4 < r['y'] < 2.8:
            has_panel = True
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for run in p.runs:
                    if not run.text.strip():
                        continue
                    f = run.font
                    fonts[f.name] += 1
                    if f.size: sizes[round(f.size.pt, 1)] += 1
                    if f.bold: bolds += 1
                    try: colors[str(f.color.rgb)] += 1
                    except Exception: pass
                    sz = round(f.size.pt, 1) if f.size else None
                    if abs(r['x']-0.49) < .03 and abs(r['y']-0.30) < .03 and sz == 16:
                        has_tag = True
                    if abs(r['x']-0.70) < .03 and abs(r['y']-0.75) < .05 and sz == 16:
                        has_lab = True
                    if abs(r['x']-0.99) < .05 and abs(r['y']-1.24) < .05 and sz == 24:
                        has_key = True
                    if 6.9 < r['y'] < 7.2 and sz in (7, 8):
                        has_foot = True
        if abs(r['x']-0.55) < .03 and abs(r['y']-0.69) < .03 and r['h'] < 0.05:
            has_rule = True
        if getattr(sh, 'has_table', False):
            t = sh.table
            for c in range(len(t.columns)):
                cell = t.cell(0, c)
                tbl_head_n += 1
                try:
                    if str(cell.fill.fore_color.rgb) == 'E1F3FF': tbl_head_ok += 1
                except Exception: pass
            last = len(t.rows) - 1
            if last > 0:
                tbl_total_n += 1
                try:
                    if str(t.cell(last, 0).fill.fore_color.rgb) == '767171': tbl_total_ok += 1
                except Exception: pass
            for row in t.rows:
                rowh_n += 1
                if round((row.height or 0)/EMU, 3) in LADDER: rowh_ok += 1
    if has_tag or has_key:
        content_slides += 1
        tags += has_tag; rules += has_rule; chevrons += has_chev
        labels += has_lab; keys += has_key; panels += has_panel; foots += has_foot

bad_fonts = {k: v for k, v in fonts.items() if k not in ALLOWED and k}
bad_sizes = {k: v for k, v in sizes.items() if k not in SZ_OK}
bad_colors = {k: v for k, v in colors.items() if k not in PALETTE}
bad_fills = {k: v for k, v in fills.items() if k not in PALETTE}

# ── 아키타입 검사 (A-01 표지 · A-03 간지 · A-10 히어로 차트)
cover_ok = div_ok = hero_ok = None
cover_got = div_got = hero_got = '해당 장 없음'
for s in prs.slides:
    shapes = []
    walk(s.shapes, shapes)
    texts = [r for r in shapes if r['sh'].has_text_frame
             and r['sh'].text_frame.text.strip()]
    big = [r for r in texts
           if any(run.font.size and run.font.size.pt >= 28
                  for p in r['sh'].text_frame.paragraphs for run in p.runs)]
    # 표지 — 전면재단 KV + 반대편 타이틀 y 2.83
    bleed = [r for r in shapes if abs(r['y']) < .01 and abs(r['h']-7.5) < .02
             and 3.0 < r['w'] < 9.0]
    if bleed and big:
        t = big[0]
        cover_ok = abs(t['y']-2.83) < .06 and t['x'] > bleed[0]['w']
        cover_got = f"KV폭 {bleed[0]['w']:.2f} · 타이틀 x{t['x']:.2f} y{t['y']:.2f}"
    # 간지 — 전폭 밴드 y 4.33 h 1.93
    band = [r for r in shapes if abs(r['x']) < .01 and abs(r['w']-13.333) < .02
            and abs(r['y']-4.33) < .06 and abs(r['h']-1.93) < .06]
    if band and big and div_ok is not True:
        div_ok = True
        div_got = f"밴드 y{band[0]['y']:.2f} h{band[0]['h']:.2f}"
    # 히어로 차트 — x 0.84 · y 2.93 · w 11.48
    for r in shapes:
        if getattr(r['sh'], 'has_chart', False) and r['w'] > 10:
            hero_ok = (abs(r['x']-0.84) < .06 and abs(r['y']-2.93) < .06
                       and abs(r['w']-11.48) < .06)
            hero_got = f"x{r['x']:.2f} y{r['y']:.2f} {r['w']:.2f}×{r['h']:.2f}"

n = max(content_slides, 1)
chk('FONT', 'SAMSUNG SS 7종만', not bad_fonts, f'위반 {len(bad_fonts)}종 {list(bad_fonts)[:3]}')
chk('BOLD', 'bold 플래그 0', bolds == 0, f'{bolds}건')
chk('SIZE', '실측 크기만', not bad_sizes, f'규격 외 {sorted(bad_sizes)[:6]}')
chk('COLOR-TXT', '팔레트 내 글자색', not bad_colors, f'외부 {sorted(bad_colors)[:5]}')
chk('COLOR-FILL', '팔레트 내 채움색', not bad_fills, f'외부 {sorted(bad_fills)[:5]}')
chk('SHADOW', '그림자 0', shadows == 0, f'{shadows}건')
chk('HDR-TAG', '태그 0.49/0.30 16pt', tags == n, f'{tags}/{n}장')
chk('HDR-RULE', '괘선 0.55/0.69', rules == n, f'{rules}/{n}장')
chk('HDR-FLAG', '셰브런 0.55/0.77', chevrons == n, f'{chevrons}/{n}장')
chk('HDR-LABEL', '라벨 0.70/0.75 16pt', labels == n, f'{labels}/{n}장')
chk('KEYMSG', '키메시지 0.99/1.24 24pt 중앙', keys == n, f'{keys}/{n}장')
chk('PANEL', '전폭 패널 y2.56', panels == n, f'{panels}/{n}장')
chk('FOOTNOTE', '각주 y7.02 8pt', foots == n, f'{foots}/{n}장')
chk('ARCH-COVER', 'A-01 KV전면재단+타이틀y2.83', cover_ok, cover_got,
    skip=cover_ok is None)
chk('ARCH-DIVIDER', 'A-03 전폭밴드 y4.33 h1.93', div_ok, div_got,
    skip=div_ok is None)
chk('ARCH-HERO', 'A-10 차트 0.84/2.93 11.48', hero_ok, hero_got,
    skip=hero_ok is None)
chk('TBL-HEAD', '표 헤더 #E1F3FF', tbl_head_ok == tbl_head_n,
    f'{tbl_head_ok}/{tbl_head_n}셀' if tbl_head_n else '표 없음 — 측정 불가',
    skip=not tbl_head_n)
chk('TBL-TOTAL', '합계행 #767171', tbl_total_ok == tbl_total_n,
    f'{tbl_total_ok}/{tbl_total_n}표' if tbl_total_n else '표 없음 — 측정 불가',
    skip=not tbl_total_n)
chk('TBL-ROWH', '행 높이 사다리', rowh_ok == rowh_n,
    f'{rowh_ok}/{rowh_n}행' if rowh_n else '표 없음 — 측정 불가',
    skip=not rowh_n)

print(f'슬라이드 {len(prs.slides)}장 (콘텐츠 {content_slides}장)\n')
print(f'{"항목":<12}{"규격":<26}{"":<3}{"실측"}')
print('─' * 78)
ok = meas = 0
for cid, spec, passed, got in results:
    mark = 'SKIP' if passed is None else ('PASS' if passed else 'FAIL')
    if passed is not None:
        meas += 1; ok += passed
    print(f'{cid:<12}{spec:<26}{mark:<6}{got}')
print('─' * 78)
print(f'준수 {ok} / {meas} 측정항목  ({100*ok//max(meas,1)}%)   · 측정불가 {len(results)-meas}건')
raise SystemExit(0 if ok == meas else 1)
