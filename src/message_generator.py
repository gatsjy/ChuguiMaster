import json
import os
from typing import Dict, Any

SETTINGS_FILE = "template_settings.json"

DEFAULT_TEMPLATES = {
    '친척/가족': {
        '참석': "{name}님, 저희 결혼식에 오셔서 자리 빛내주시고 따뜻하게 축복해 주셔서 정말 감사합니다. 보내주신 아낌없는 사랑과 정성 잊지 않고 늘 행복하게 잘 살겠습니다. 항상 건강하세요!",
        '불참(송금)': "{name}님, 소중한 축의금과 따뜻한 축하 말씀에 진심으로 감사드립니다. 직접 모시지 못해 아쉽지만, 조만간 찾아뵙고 정식으로 인사드리겠습니다!"
    },
    '직장/기관': {
        '참석': "{name} 님, 바쁘신 와중에도 저희 결혼식에 참석해 주셔서 진심으로 감사드립니다. 전해주신 따뜻한 축하와 격려 말씀 가슴 깊이 새기며 예쁘고 행복하게 살겠습니다.",
        '불참(송금)': "{name} 님, 전해주신 소중한 축의와 따뜻한 마음에 깊이 감사드립니다. 직접 인사드리지 못해 아쉽지만, 조만간 감사한 마음을 담아 인사드리겠습니다."
    },
    '종교/모임': {
        '참석': "{name} 님, 저희 결혼식에 오셔서 따뜻한 기도와 축복을 나누어 주셔서 진심으로 감사드립니다. 주신 축복에 보답하며 늘 기쁨과 사랑이 넘치는 가정을 이루겠습니다.",
        '불참(송금)': "{name} 님, 마음 담아 전해주신 소중한 축의와 축복의 기도에 감사드립니다. 보답하는 마음으로 늘 예쁘게 살아가겠습니다."
    },
    '학교/동창': {
        '참석': "{name}야! 와줘서 진짜 고맙다! 멀리서 오느라 고생 많았지? 덕분에 너무 든든했고 기뻤다. 신혼여행 다녀와서 조만간 맛있는 거 먹자!",
        '불참(송금)': "{name}야, 사정 때문에 오지 못했지만 마음 담아 보내준 축의금 정말 고마워! 조만간 만나서 맛있는 거 먹으며 이야기 나누자!"
    },
    '지인/기타': {
        '참석': "{name} 님, 저희 결혼식에 참석해 주셔서 진심으로 감사드립니다. 보내주신 축복에 보답하며 예쁘고 행복하게 살아가겠습니다. 늘 건강하세요!",
        '불참(송금)': "{name} 님, 소중한 축하와 축의를 전해 주셔서 깊이 감사드립니다. 따뜻한 마음 항상 간직하겠습니다."
    }
}

class MessageGenerator:
    _templates = None

    @classmethod
    def get_templates(cls) -> Dict[str, Dict[str, str]]:
        if cls._templates is None:
            cls.load_templates()
        return cls._templates

    @classmethod
    def load_templates(cls):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    cls._templates = json.load(f)
                    return
            except Exception as e:
                print("Failed to load settings file:", e)
        
        # 기본값 로드 및 생성
        cls._templates = json.loads(json.dumps(DEFAULT_TEMPLATES))

    @classmethod
    def save_templates(cls, new_templates: Dict[str, Dict[str, str]]):
        cls._templates = new_templates
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(new_templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Failed to save settings file:", e)

    @classmethod
    def reset_templates(cls):
        cls._templates = json.loads(json.dumps(DEFAULT_TEMPLATES))
        if os.path.exists(SETTINGS_FILE):
            try:
                os.remove(SETTINGS_FILE)
            except Exception:
                pass

    @classmethod
    def generate(cls, guest: Dict[str, Any]) -> str:
        name = guest.get('name', '손님')
        relation = guest.get('relation', '지인/기타')
        attended_status = guest.get('attended', '참석')
        
        if '&' in name:
            display_name = f"{name} 분"
        else:
            display_name = name
            
        templates = cls.get_templates()
        rel_templates = templates.get(relation, templates.get('지인/기타', DEFAULT_TEMPLATES['지인/기타']))
        template = rel_templates.get(attended_status, rel_templates.get('참석', "{name}님 감사합니다."))
        
        return template.format(name=display_name)
