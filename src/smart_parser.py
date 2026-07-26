import re
import pandas as pd
from typing import List, Dict, Any

class SmartParser:
    """
    카톡/메모장의 자유 서식 텍스트 또는 엑셀 데이터를 자동 파싱하여 표준 하객 데이터로 변환하는 클래스
    """
    
    RELATION_KEYWORDS = {
        '직장': ['직장', '회사', '팀장', '부장', '과장', '대리', '사원', '대표', '동료', '선배', '후배', '업무'],
        '친척': ['친척', '삼촌', '이모', '고모', '사촌', '숙부', '외삼촌', '가족', '친지'],
        '대학': ['대학', '동기', '학부', '캠퍼스'],
        '고교/초중': ['고교', '고등', '중학', '초등', '동창', '학교', '친구'],
        '지인/기타': ['기타', '지인', '모임', '이웃']
    }

    @staticmethod
    def parse_amount(text: str) -> int:
        """
        금액 파싱 (예: 10만원 -> 100000, 5만 -> 50000, 50,000 -> 50000)
        """
        text_clean = text.replace(',', '').strip()
        
        # 10만원, 5만 형태
        man_match = re.search(r'(\d+)\s*만\s*원?', text_clean)
        if man_match:
            return int(man_match.group(1)) * 10000
        
        # 50000 / 100000 형태
        num_matches = re.findall(r'\b\d{4,8}\b', text_clean)
        if num_matches:
            return int(num_matches[0])
            
        return 0

    @classmethod
    def parse_relation(cls, text: str) -> str:
        for category, keywords in cls.RELATION_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return category
        return '지인/기타'

    @classmethod
    def parse_single_line(cls, line: str, line_num: int) -> Dict[str, Any]:
        line = line.strip()
        
        # 식권 수 파싱 (예: 식권2, 식권 2장, 2장)
        tickets = 1
        ticket_match = re.search(r'식권\s*(\d+)', line)
        if ticket_match:
            tickets = int(ticket_match.group(1))
        elif '불참' in line or '송금' in line:
            tickets = 0

        # 참석 여부
        is_attended = False if ('불참' in line or '송금' in line or '모바일' in line) else True
        
        # 수령 방법
        payment_type = '계좌이체' if ('계좌' in line or '송금' in line or '이체' in line) else '현금'
        
        # 금액 파싱
        amount = cls.parse_amount(line)
        
        # 관계 파싱
        relation = cls.parse_relation(line)
        
        # 이름 추출 (한글 2~4자 또는 영문 이름 우선 탐색)
        name = f"하객{line_num}"
        # 한글 이름 패턴 탐색 (예: 홍길동, 이영희)
        name_match = re.search(r'([가-힣]{2,4})', line)
        if name_match:
            # 키워드가 아닌 한글 단어 선별
            candidates = re.findall(r'([가-힣]{2,4})', line)
            excluded = ['식권', '불참', '송금', '계좌', '이체', '현금', '직장', '회사', '대학', '친척', '동기', '친구', '지인', '만원', '참석']
            for cand in candidates:
                if cand not in excluded:
                    name = cand
                    break

        return {
            'id': line_num,
            'name': name,
            'amount': amount,
            'relation': relation,
            'tickets': tickets if is_attended else 0,
            'attended': '참석' if is_attended else '불참(송금)',
            'payment': payment_type,
            'sent_thanks': False,
            'raw': line
        }

    @classmethod
    def parse_text_lines(cls, raw_text: str) -> List[Dict[str, Any]]:
        results = []
        lines = raw_text.strip().split('\n')
        
        for idx, line in enumerate(lines, 1):
            if line.strip():
                results.append(cls.parse_single_line(line, idx))
                
        return results

    @classmethod
    def parse_excel(cls, file_path: str) -> List[Dict[str, Any]]:
        df = pd.read_excel(file_path)
        results = []
        
        name_col = next((c for c in df.columns if any(k in str(c) for k in ['이름', '성함', '입금자', '하객'])), df.columns[0])
        amount_col = next((c for c in df.columns if any(k in str(c) for k in ['금액', '축의', '입금'])), None)
        
        for idx, row in df.iterrows():
            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else f"하객{idx+1}"
            raw_amt = str(row[amount_col]) if amount_col and pd.notna(row[amount_col]) else "0"
            amount = cls.parse_amount(raw_amt)
            
            row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
            relation = cls.parse_relation(row_str)
            
            results.append({
                'id': idx + 1,
                'name': name,
                'amount': amount,
                'relation': relation,
                'tickets': 1,
                'attended': '참석',
                'payment': '엑셀가져오기',
                'sent_thanks': False,
                'raw': row_str
            })
            
        return results
