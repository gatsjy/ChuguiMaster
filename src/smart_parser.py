import re
import pandas as pd
from typing import List, Dict, Any

class SmartParser:
    """
    실제 축의금 리스트 엑셀 양식(순번, 성명, 금액, 소속, 비고) 및 복수 이름(김해수,김유지/김재경(조외순))을
    완벽하게 지원하는 파서 모듈
    """
    
    RELATION_KEYWORDS = {
        '친척/가족': ['이모', '할머니', '삼촌', '고모', '숙부', '친척', '외삼촌', '가족', '친지', '처남', '처형'],
        '직장/기관': ['보건소', '보건지소', '보건지구', '지소', '병원', '회사', '팀장', '부장', '과장', '대리', '사원', '대표', '동료', '직장', '소속'],
        '종교/모임': ['교회', '성당', '사찰', '모임', '선교회', '구역'],
        '학교/동창': ['대학', '고교', '고등', '중학', '초등', '동창', '동기', '친구'],
        '지인/기타': ['기타', '지인', '이웃', '지역']
    }

    @staticmethod
    def parse_amount(val: Any) -> int:
        """
        금액 파싱 (예: 2,000,000, 100000, '10만원', '5만')
        """
        if pd.isna(val) or not val:
            return 0
            
        if isinstance(val, (int, float)):
            return int(val)
            
        text = str(val).replace(',', '').strip()
        
        # 10만원, 5만 형태
        man_match = re.search(r'(\d+)\s*만\s*원?', text)
        if man_match:
            return int(man_match.group(1)) * 10000
        
        # 순수 숫자 추출
        num_matches = re.findall(r'\d+', text)
        if num_matches:
            num_str = "".join(num_matches)
            val_int = int(num_str)
            if val_int < 1000: # 예: 10 -> 10만원
                return val_int * 10000
            return val_int
            
        return 0

    @classmethod
    def parse_relation(cls, text: str) -> str:
        for category, keywords in cls.RELATION_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return category
        return '지인/기타'

    @classmethod
    def format_display_name(cls, raw_name: str) -> str:
        """
        '김해수,김유지' -> '김해수 & 김유지'
        '김재경(조외순)' -> '김재경 (조외순)'
        """
        name = raw_name.strip()
        if ',' in name:
            names = [n.strip() for n in name.split(',') if n.strip()]
            return " & ".join(names)
        return name

    @classmethod
    def parse_text_lines(cls, raw_text: str) -> List[Dict[str, Any]]:
        results = []
        lines = raw_text.strip().split('\n')
        
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            if not line_str:
                continue
                
            # 식권 수 파싱 (대인/소인 구분 지원)
            adult_tickets = 1
            child_tickets = 0
            
            ticket_match = re.search(r'식권\s*(\d+)', line_str)
            if ticket_match:
                adult_tickets = int(ticket_match.group(1))
            elif '불참' in line_str or '송금' in line_str:
                adult_tickets = 0

            child_match = re.search(r'소인\s*(\d+)', line_str)
            if child_match:
                child_tickets = int(child_match.group(1))

            is_attended = False if ('불참' in line_str or '송금' in line_str) else True
            payment_type = '계좌이체' if ('계좌' in line_str or '송금' in line_str or '이체' in line_str) else '현금'
            amount = cls.parse_amount(line_str)
            relation = cls.parse_relation(line_str)
            
            # 이름 파싱
            tokens = line_str.split()
            raw_name = f"하객{idx}"
            for token in tokens:
                cleaned = re.sub(r'[\d만,원식권불참송금현금계좌이체]', '', token).strip()
                if cleaned and len(cleaned) >= 2 and not any(kw in cleaned for kw in ['보건', '교회', '이모', '친척', '할머니']):
                    raw_name = token
                    break

            results.append({
                'id': idx,
                'name': cls.format_display_name(raw_name),
                'raw_name': raw_name,
                'amount': amount,
                'relation': relation,
                'adult_tickets': adult_tickets if is_attended else 0,
                'child_tickets': child_tickets,
                'attended': '참석' if is_attended else '불참(송금)',
                'payment': payment_type,
                'note': '',
                'sent_thanks': False,
                'raw': line_str
            })
            
        return results

    @classmethod
    def parse_excel(cls, file_path: str) -> List[Dict[str, Any]]:
        """
        사용자 실제 이미지 양식 (순번, 성명, 금액, 소속, 비고) 지원 파서
        """
        df = pd.read_excel(file_path)
        results = []
        
        # 헤더 자동 찾기
        name_col = next((c for c in df.columns if any(k in str(c) for k in ['성명', '이름', '입금자'])), df.columns[0])
        amount_col = next((c for c in df.columns if any(k in str(c) for k in ['금액', '축의금', '입금'])), None)
        belong_col = next((c for c in df.columns if any(k in str(c) for k in ['소속', '관계', '그룹'])), None)
        note_col = next((c for c in df.columns if any(k in str(c) for k in ['비고', '특이사항', '메모'])), None)
        
        for idx, row in df.iterrows():
            raw_name = str(row[name_col]).strip() if pd.notna(row[name_col]) else f"하객{idx+1}"
            if raw_name == 'nan' or not raw_name or '성명' in raw_name or '한주안' in raw_name and idx == 0:
                # 헤더 샘플행 스킵
                continue
                
            raw_amt = row[amount_col] if amount_col and pd.notna(row[amount_col]) else 0
            amount = cls.parse_amount(raw_amt)
            
            belong_str = str(row[belong_col]) if belong_col and pd.notna(row[belong_col]) else ""
            note_str = str(row[note_col]) if note_col and pd.notna(row[note_col]) else ""
            
            combined_info = f"{belong_str} {note_str}".strip()
            relation = cls.parse_relation(combined_info)
            
            payment_type = '계좌이체' if '계좌' in note_str or '이체' in note_str else '현금'
            is_attended = False if '불참' in note_str else True

            results.append({
                'id': len(results) + 1,
                'name': cls.format_display_name(raw_name),
                'raw_name': raw_name,
                'amount': amount,
                'relation': relation if belong_str else cls.parse_relation(raw_name),
                'belong': belong_str,
                'adult_tickets': 1 if is_attended else 0,
                'child_tickets': 0,
                'attended': '참석' if is_attended else '불참(송금)',
                'payment': payment_type,
                'note': note_str,
                'sent_thanks': False,
                'raw': f"{raw_name} {amount} {belong_str} {note_str}".strip()
            })
            
        return results
