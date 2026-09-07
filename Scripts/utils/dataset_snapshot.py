# -*- coding: utf-8 -*-
"""
파싱 데이터셋 스냅샷 저장·복원

`CampaignDataset` 은 인메모리 객체라 브라우저를 닫으면 사라진다. 파싱에 수 분이
걸리고 결손 항목(기간·KPI 목표 등)은 기획자가 손으로 채운 값이므로, 그 결과를
잃으면 처음부터 다시 해야 한다.

스냅샷은 감사 기록이 아니라 **작업 이어하기** 용도이므로 Knowledge 스냅샷과
같은 타임스탬프로 짝을 맞춰 저장한다.
  Output/Temp/Draft_Knowledge_YYMMDD_HHMMSS.json
  Output/Temp/Draft_Dataset_YYMMDD_HHMMSS.json

경로는 저장하지 않는다 (데이터셋에는 파일명만 들어감 — 이식성 확보).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from models.campaign_data import CampaignDataset
from utils.serialization import normalize_for_json


PREFIX = 'Draft_Dataset_'


def save(dataset: CampaignDataset, output_dir: str,
         timestamp: Optional[str] = None) -> str:
    """
    데이터셋을 JSON 스냅샷으로 저장한다.

    Args:
        dataset: 저장할 데이터셋
        output_dir: 저장 폴더 (없으면 만든다)
        timestamp: Knowledge 스냅샷과 짝을 맞출 타임스탬프 (YYMMDD_HHMMSS)

    Returns:
        저장된 파일 경로
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime('%y%m%d_%H%M%S')
    path = out / f'{PREFIX}{stamp}.json'

    data = normalize_for_json(dataset.to_dict())
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
    return str(path)


def load(file_path: str) -> CampaignDataset:
    """
    스냅샷에서 데이터셋을 복원한다.

    Args:
        file_path: Draft_Dataset_*.json 경로

    Returns:
        복원된 CampaignDataset
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return CampaignDataset.from_dict(json.load(f))


def list_snapshots(output_dir: str, limit: int = 10
                   ) -> List[Tuple[str, str]]:
    """
    최근 스냅샷 목록 (최신 순).

    Returns:
        [(표시명, 경로)] — 표시명은 'YYMMDD HH:MM:SS' 형식
    """
    out = Path(output_dir)
    if not out.is_dir():
        return []
    files = sorted(out.glob(f'{PREFIX}*.json'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    items: List[Tuple[str, str]] = []
    for p in files[:limit]:
        stamp = p.stem[len(PREFIX):]
        if len(stamp) == 13:
            label = f'{stamp[:6]} {stamp[7:9]}:{stamp[9:11]}:{stamp[11:13]}'
        else:
            label = stamp
        items.append((label, str(p)))
    return items


def knowledge_pair(dataset_path: str) -> Optional[str]:
    """같은 타임스탬프의 Knowledge 스냅샷 경로 (없으면 None)"""
    p = Path(dataset_path)
    stamp = p.stem[len(PREFIX):]
    candidate = p.with_name(f'Draft_Knowledge_{stamp}.json')
    return str(candidate) if candidate.exists() else None
