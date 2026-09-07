# -*- coding: utf-8 -*-
"""
Data Validator - Validate Campaign Knowledge data
"""

from typing import List
from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem


class DataValidator:
    """Campaign Knowledge의 데이터를 검증합니다"""

    @staticmethod
    def validate(knowledge: CampaignKnowledge) -> None:
        """
        Campaign Knowledge 전체를 검증합니다.

        Args:
            knowledge: 검증할 CampaignKnowledge 객체
        """
        # 1. 필수 파일 존재 여부
        DataValidator._validate_file_presence(knowledge)

        # 2. 인코딩 검증
        DataValidator._validate_encoding(knowledge)

        # 3. 데이터 완전성
        DataValidator._validate_data_completeness(knowledge)

        # 4. 데이터 일관성
        DataValidator._validate_data_coherence(knowledge)

        # 5. 이상치 탐지
        DataValidator._detect_anomalies(knowledge)

    @staticmethod
    def _validate_file_presence(knowledge: CampaignKnowledge) -> None:
        """필수 파일 존재 여부 검증"""
        if knowledge.proposal['status'] == 'missing' and knowledge.postbuy['status'] == 'missing':
            knowledge.add_checklist_item(ChecklistItem(
                type='input_missing',
                severity='error',
                message='필수 입력 파일 없음',
                detail='제안서와 포스트바이 파일 모두 없습니다',
                source='validator:_validate_file_presence'
            ))
        elif knowledge.proposal['status'] == 'missing':
            knowledge.add_checklist_item(ChecklistItem(
                type='input_missing',
                severity='warning',
                message='제안서 파일 누락',
                detail='제안서(Proposal) 파일을 찾을 수 없습니다',
                source='validator:_validate_file_presence'
            ))
        elif knowledge.postbuy['status'] == 'missing':
            knowledge.add_checklist_item(ChecklistItem(
                type='input_missing',
                severity='warning',
                message='포스트바이 파일 누락',
                detail='포스트바이(PostBuy) 리포트 파일을 찾을 수 없습니다',
                source='validator:_validate_file_presence'
            ))

    @staticmethod
    def _validate_encoding(knowledge: CampaignKnowledge) -> None:
        """인코딩 검증"""
        proposal_encoding = knowledge.proposal.get('encoding', 'utf-8')
        postbuy_encoding = knowledge.postbuy.get('encoding', 'utf-8')

        knowledge.validation['encoding_status']['proposal_encoding'] = proposal_encoding
        knowledge.validation['encoding_status']['postbuy_encoding'] = postbuy_encoding

        if proposal_encoding and proposal_encoding.lower() != 'utf-8':
            knowledge.add_checklist_item(ChecklistItem(
                type='encoding_mismatch',
                severity='warning',
                message=f'제안서 인코딩 확인 필요',
                detail=f'제안서가 {proposal_encoding} 인코딩입니다. UTF-8 권장',
                source='validator:_validate_encoding'
            ))

        if postbuy_encoding and postbuy_encoding.lower() != 'utf-8':
            knowledge.add_checklist_item(ChecklistItem(
                type='encoding_mismatch',
                severity='warning',
                message=f'포스트바이 인코딩 확인 필요',
                detail=f'포스트바이가 {postbuy_encoding} 인코딩입니다. UTF-8 권장',
                source='validator:_validate_encoding'
            ))

    @staticmethod
    def _validate_data_completeness(knowledge: CampaignKnowledge) -> None:
        """데이터 완전성 검증"""
        # 제안서 KPI 확인
        if knowledge.proposal['status'] == 'found' and not knowledge.proposal.get('kpi_plan'):
            knowledge.add_checklist_item(ChecklistItem(
                type='data_incomplete',
                severity='info',
                message='제안서 KPI 정보',
                detail='제안서에서 명확한 KPI 정보를 자동 추출할 수 없습니다. 수동 확인 권고',
                source='validator:_validate_data_completeness'
            ))

        # 포스트바이 KPI 확인
        if knowledge.postbuy['status'] == 'found' and not knowledge.postbuy.get('kpi_actual'):
            knowledge.add_checklist_item(ChecklistItem(
                type='data_incomplete',
                severity='info',
                message='포스트바이 KPI 정보',
                detail='포스트바이에서 명확한 KPI 정보를 자동 추출할 수 없습니다. 수동 확인 권고',
                source='validator:_validate_data_completeness'
            ))

    @staticmethod
    def _validate_data_coherence(knowledge: CampaignKnowledge) -> None:
        """데이터 일관성 검증 (제안서 vs 포스트바이)"""
        # 기간 검증
        proposal_period = knowledge.proposal.get('metadata', {}).get('campaign_period')
        postbuy_period = knowledge.postbuy.get('metadata', {}).get('report_period')

        if proposal_period and postbuy_period:
            if proposal_period.replace(' ', '') != postbuy_period.replace(' ', ''):
                knowledge.add_checklist_item(ChecklistItem(
                    type='time_range_mismatch',
                    severity='warning',
                    message='기간 범위 불일치',
                    detail=f'제안: {proposal_period} / 포스트바이: {postbuy_period}',
                    source='validator:_validate_data_coherence'
                ))

    @staticmethod
    def _detect_anomalies(knowledge: CampaignKnowledge) -> None:
        """이상치 탐지"""
        # 포스트바이의 수치 검증
        for kpi in knowledge.postbuy.get('kpi_actual', []):
            data = kpi.get('data', [])
            for row in data:
                try:
                    # 숫자값 찾기
                    if isinstance(row, (list, tuple)):
                        for item in row:
                            if isinstance(item, (int, float)) and item < 0:
                                knowledge.add_checklist_item(ChecklistItem(
                                    type='data_anomaly',
                                    severity='error',
                                    message='이상치: 음수값',
                                    detail=f'포스트바이에서 음수값이 발견되었습니다: {item}',
                                    source='validator:_detect_anomalies'
                                ))
                except:
                    pass
