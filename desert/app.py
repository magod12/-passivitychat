import json
import re
import difflib
import time
import logging
import os
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# 로깅 설정 (환경별)
log_level = logging.WARNING if os.environ.get('FLASK_ENV') == 'production' else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 전역 변수
BASE_DIR = Path(__file__).parent
LEARNED_OVERRIDES_FILE = BASE_DIR / "learned_overrides.json"
ANSWER_FEEDBACK_FILE = BASE_DIR / "answer_feedback.json"

# 학습된 오버라이드 로드
try:
    with open(LEARNED_OVERRIDES_FILE, "r", encoding="utf-8") as f:
        LEARNED_OVERRIDES = json.load(f)
except FileNotFoundError:
    LEARNED_OVERRIDES = []

# 정답 피드백 로드
try:
    with open(ANSWER_FEEDBACK_FILE, "r", encoding="utf-8") as f:
        ANSWER_FEEDBACK = json.load(f)
except FileNotFoundError:
    ANSWER_FEEDBACK = []

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# 성능 최적화를 위한 캐시 (OrderedDict 사용)
_question_cache = OrderedDict()
_cache_max_size = 1000
_performance_stats = {
    "cache_hits": 0,
    "cache_misses": 0,
    "total_questions": 0,
    "cache_evictions": 0
}

# 세션 초기화 함수
def init_session():
    if 'tokens_left' not in session:
        session['tokens_left'] = 20
    if 'used_hints' not in session:
        session['used_hints'] = []

# 사막 시나리오 데이터
SCENARIO = {
    "id": "desert_man",
    "title": "사막의 남자",
    "description": "사막에서 발견된 남자의 시체와 관련된 미스터리",
    "facts": [
        "남자는 열기구를 타고 여행 중이었습니다",
        "열기구에 문제가 생겨 하강하고 있었습니다",
        "짐과 옷을 모두 버렸지만 여전히 하강했습니다",
        "마지막으로 성냥으로 제비뽑기를 했습니다",
        "남자가 부러진 성냥을 뽑아 희생했습니다",
        "남자는 열기구에서 뛰어내려 사망했습니다"
    ],
    "hints": [
        "남자는 열기구를 타고 여행중이었습니다.",
        "남자의 죽음은 스스로의 선택이었습니다.",
        "남자는 성냥을 이용한 제비뽑기를 하였습니다."
    ]
}

# 사막 시나리오 상수들
class DesertConstants:
    CORE_KEYWORDS = ["열기구","성냥","제비","제비뽑기","사막","추락","낙하","하강","무게","알몸","희생","떨어져","뛰어내"]
    
    # 무의미한 질문 패턴들
    NONSENSE_PATTERNS = [
        "공룡", "운석", "마법", "외계인", "로봇", "시간여행", "차원", "포털",
        "유령", "귀신", "영혼", "저주", "좀비", "뱀파이어", "늑대인간", "드래곤", "요정", "엘프",
        "중력", "자기장", "방사능", "핵폭탄", "미사일", "레이저", "플라즈마",
        "발걸기", "발을 걸어", "발걸어", "넘어뜨려", "넘어뜨려서", "넘어뜨렸",
        "태풍", "허리케인", "사이클론", "토네이도", "회오리", "눈사태", "산사태", "토사류", "토석류",
        "지진", "해일", "쓰나미", "화산", "용암", "홍수", "가뭄", "폭설", "우박", "번개", "천둥",
        # 새로 추가된 무의미한 패턴들 (피드백 기반)
        "익사", "익사했", "익사하여", "물에", "물속에", "물에서", "물로",
        "질식", "질식했", "질식하여", "질식해서", "숨이", "숨을", "숨막혀",
        "알레르기", "알레르기로", "알레르기 때문에", "알레르기로 인해",
        "독", "독으로", "독 때문에", "독으로 인해", "중독", "중독되어",
        "심장마비", "심장", "마비", "심장마비로", "심장마비 때문에",
        "뇌졸중", "뇌", "졸중", "뇌졸중으로", "뇌졸중 때문에",
        "암", "암으로", "암 때문에", "암으로 인해", "질병", "병으로",
        "더위", "더워서", "더위에", "더위로", "더위 때문에", "더위로 인해",
        "추위", "추워서", "추위에", "추위로", "추위 때문에", "추위로 인해",
        "오아시스", "오아시스에", "오아시스에서", "오아시스로",
        "모래폭풍", "모래폭풍에", "모래폭풍으로", "모래폭풍 때문에",
        "교통사고", "교통사고로", "교통사고 때문에", "교통사고로 인해",
        "자동차", "자동차로", "자동차에", "자동차에서", "자동차 때문에",
        "비행기", "비행기로", "비행기에", "비행기에서", "비행기 때문에",
        "배", "배로", "배에", "배에서", "배 때문에",
        "하마", "하마로", "하마에", "하마에서", "하마 때문에",
        "말", "말로", "말에", "말에서", "말 때문에",
        "낙타", "낙타로", "낙타에", "낙타에서", "낙타 때문에",
        "코끼리", "코끼리로", "코끼리에", "코끼리에서", "코끼리 때문에",
        "기린", "기린으로", "기린에", "기린에서", "기린 때문에",
        "사자", "사자로", "사자에", "사자에서", "사자 때문에",
        "호랑이", "호랑이로", "호랑이에", "호랑이에서", "호랑이 때문에",
        "곰", "곰으로", "곰에", "곰에서", "곰 때문에",
        "늑대", "늑대로", "늑대에", "늑대에서", "늑대 때문에",
        "여우", "여우로", "여우에", "여우에서", "여우 때문에",
        "자전거", "자전거로", "자전거에", "자전거에서", "자전거 때문에",
        "오토바이", "오토바이로", "오토바이에", "오토바이에서", "오토바이 때문에",
        "기차", "기차로", "기차에", "기차에서", "기차 때문에",
        "지하철", "지하철로", "지하철에", "지하철에서", "지하철 때문에",
        "버스", "버스로", "버스에", "버스에서", "버스 때문에",
        "트럭", "트럭으로", "트럭에", "트럭에서", "트럭 때문에",
        "택시", "택시로", "택시에", "택시에서", "택시 때문에",
        "스쿠터", "스쿠터로", "스쿠터에", "스쿠터에서", "스쿠터 때문에",
        "헬리콥터", "헬리콥터로", "헬리콥터에", "헬리콥터에서", "헬리콥터 때문에",
        "글라이더", "글라이더로", "글라이더에", "글라이더에서", "글라이더 때문에",
        "패러글라이딩", "패러글라이드", "패러글라이딩으로", "패러글라이드로",
        "스카이다이빙", "스카이 다이빙", "스카이다이빙으로", "스카이 다이빙으로",
        "번지점프", "번지점프로", "번지점프에", "번지점프에서", "번지점프 때문에",
        "깃발", "깃발을", "깃발로", "깃발에", "깃발에서", "깃발 때문에",
        "신호", "신호를", "신호로", "신호에", "신호에서", "신호 때문에",
        "구조", "구조를", "구조로", "구조에", "구조에서", "구조 때문에",
        "구조신호", "구조신호를", "구조신호로", "구조신호에", "구조신호에서", "구조신호 때문에",
        "깃발을", "신호를", "구조를", "타인이", "다른 사람이", "일행이", "동료가",
        "벗겨", "벗겼", "벗겨서", "스스로", "자발적으로", "스스로의", "자신의",
        "선택으로", "선택이", "부끄러움", "창피", "수치", "부끄러워", "창피해", "수치스러워",
        "무게중심", "중심을", "잘못", "잘못 잡아", "잘못 잡아서", "싸움", "다툼", "갈등",
        "싸워", "다투어", "갈등하여", "밀려", "밀어서", "밀렸", "강요", "강요하여",
        "강요해서", "강제로", "강제하여", "강제해서", "사고로", "사고가", "놀다가", "놀면서", "놀고",
        "놀아", "재미로", "장난으로", "장난삼아", "실수로", "실수하여", "실수해서",
        "부주의로", "부주의하여", "부주의해서", "게임", "내기", "가벼운", "가벼운 게임",
        "가벼운 내기", "재미있는", "재미있는 게임"
    ]
    
    # 오답 패턴들
    WRONG_ANSWER_PATTERNS = [
        "낙타", "선인장", "길을 잃", "물이 없", "더위에", "더워서", "추워서"
    ]
    
    # 신체적 증거 관련 질문들 (모두 "예"가 정답)
    PHYSICAL_EVIDENCE_QUESTIONS = [
        # 기본 낙상/추락 관련
        "낙상", "떨어져", "떨어졌", "떨어져서", "떨어져 죽", "떨어져 사망",
        "추락", "추락했", "추락하여", "추락해서", "추락으로",
        "충격", "충격을", "충격으로", "충격받", "충격받았",
        
        # 일반적인 상처/부상
        "상처", "다쳤", "다쳤나", "다친", "다친 상태", "부상", "외상",
        "크게 다쳤", "심하게 다쳤", "심각하게 다쳤", "심각한 부상",
        "부러졌", "부러졌나", "골절", "뼈가 부러", "뼈가 부러졌",
        
        # 구체적인 신체 부위별 손상
        "목이", "목이 부러", "목이 부러졌", "목 부러", "목 골절",
        "팔이", "팔이 부러", "팔이 부러졌", "팔 부러", "팔 골절",
        "다리가", "다리가 부러", "다리가 부러졌", "다리 부러", "다리 골절",
        "갈비뼈", "갈비뼈가", "갈비뼈가 나갔", "갈비뼈가 부러", "갈비뼈 골절",
        "발목이", "발목이 부러", "발목이 부러졌", "발목 부러", "발목 골절",
        "머리가", "머리가 다쳤", "머리 부상", "두부", "두부 손상",
        "척추", "척추가", "척추가 부러", "척추 골절", "척추 손상",
        "어깨", "어깨가", "어깨가 부러", "어깨 골절",
        "손목", "손목이", "손목이 부러", "손목 골절",
        "무릎", "무릎이", "무릎이 부러", "무릎 골절",
        "발가락", "발가락이", "발가락이 부러", "발가락 골절",
        "손가락", "손가락이", "손가락이 부러", "손가락 골절",
        
        # 내부 장기 손상
        "내장", "내장이", "내장이 터졌", "내장 손상", "내부 장기",
        "간", "간이", "간이 터졌", "간 손상", "간 파열",
        "폐", "폐가", "폐가 터졌", "폐 손상", "폐 파열",
        "심장", "심장이", "심장이 터졌", "심장 손상", "심장 파열",
        "신장", "신장이", "신장이 터졌", "신장 손상", "신장 파열",
        "비장", "비장이", "비장이 터졌", "비장 손상", "비장 파열",
        "위", "위가", "위가 터졌", "위 손상", "위 파열",
        "장", "장이", "장이 터졌", "장 손상", "장 파열",
        
        # 출혈 관련
        "출혈", "피가", "피가 나", "피가 흘렀", "피 흘렀",
        "내출혈", "내부 출혈", "뇌출혈", "뇌 내출혈",
        
        # 손에 들고 있던 것
        "손에", "손에 무언가", "손에 들", "손에 들려", "손에 들고",
        "손에 쥐", "손에 쥐고", "손에 쥐었", "손에 쥐고 있",
        
        # 몸 상태
        "몸에", "몸에 상처", "몸에 무언가", "몸 상태", "몸이 정상",
        "정상이 아닌", "이상한", "이상한가", "상태가 이상",
        "다쳤나", "다친 상태인", "다쳤나요", "다친 상태인가요",
        "손상", "손상되었", "손상된", "손상된 상태",
        "파열", "파열되었", "파열된", "파열된 상태",
        "부러진", "부러진 상태", "부러진 것",
        
        # 기타 신체 변화
        "멍", "멍이", "멍이 들었", "멍이 생겼",
        "부종", "부어", "부어있", "부어서",
        "변형", "변형되었", "변형된", "변형된 상태",
        "절단", "절단되었", "절단된", "절단된 상태",
        
        # 몸 상태 관련 (떨어져서 죽었으므로 상처가 있고 다쳐있어야 정상)
        "몸이", "몸이 깨끗", "몸이 깨끗한", "몸이 깨끗한가",
        "깨끗", "깨끗한", "깨끗한가", "깨끗한가요",
        "정상", "정상인", "정상인가", "정상인가요",
        "상처가 없", "상처가 없나", "상처가 없나요",
        "다치지 않", "다치지 않았", "다치지 않았나",
        "부상이 없", "부상이 없나", "부상이 없나요",
        "손상이 없", "손상이 없나", "손상이 없나요",
        "건강", "건강한", "건강한가", "건강한가요",
        "무사", "무사한", "무사한가", "무사한가요"
    ]
    
    # 금지된 오프-시나리오 용어들
    BANNED_OFF_SCENARIO = [
        "스카이다이빙", "패러글라이딩", "패러글라이드", "베이스점프", "스카이 다이빙",
        "낙하산", "윙슈트", "번지점프", "행글라이딩", "행글라이더"
    ]

# 유틸리티 함수들
def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

def is_negative_question(question: str) -> bool:
    """부정의문문인지 확인"""
    negative_patterns = [
        "아닙니까", "아니야", "아니지", "아닌가", "아닐까", 
        "아닌가요", "아닐까요", "아니죠", "아닌가요", "아닐까요",
        "아니라고", "아니라", "아닌", "아니"
    ]
    return any(pattern in question for pattern in negative_patterns)

def convert_negative_question(question: str) -> str:
    """부정의문문을 긍정문으로 변환"""
    if not is_negative_question(question):
        return question
    
    # 부정 표현 제거
    question = question.replace("아닙니까", "입니까")
    question = question.replace("아니야", "야")
    question = question.replace("아니지", "지")
    question = question.replace("아닌가", "인가")
    question = question.replace("아닐까", "일까")
    question = question.replace("아닌가요", "인가요")
    question = question.replace("아닐까요", "일까요")
    question = question.replace("아니죠", "죠")
    question = question.replace("아니라고", "라고")
    question = question.replace("아니라", "라")
    question = question.replace("아닌", "인")
    question = question.replace("아니", "이")
    
    return question

def is_meaningful_question(question: str) -> bool:
    """질문이 추리와 관련된 의미있는 질문인지 판단 (강화된 버전)"""
    q = normalize_text(question)
    
    # 1. 시나리오 핵심 키워드 포함 여부 (강화)
    scenario_keywords = [
        # 사건 핵심 요소
        "남자", "열기구", "성냥", "제비뽑기", "사막", "죽음", "사망", "추락", "낙하", "하강", 
        "무게", "알몸", "희생", "떨어져", "뛰어내", "일행", "여행", "고장", "문제"
    ]
    has_scenario_keyword = any(keyword in q for keyword in scenario_keywords)
    
    # 시나리오와 무관한 키워드가 있으면 무의미한 질문으로 분류
    irrelevant_keywords = [
        "매", "들쥐", "차", "원피스", "미어켓", "동물", "새", "포유동물", "옷", "의류",
        "자동차", "차량", "교통수단", "패션", "의상", "스타일"
    ]
    has_irrelevant_keyword = any(keyword in q for keyword in irrelevant_keywords)
    
    if has_irrelevant_keyword and not has_scenario_keyword:
        return False
    
    # 2. 질문 형태인지 확인 (강화)
    question_words = ["왜", "어떻게", "언제", "어디서", "무엇", "누구", "어떤", "?", "나요", "습니까", "인가요", "죽었나요", "죽었어요"]
    is_question_form = any(word in q for word in question_words)
    
    # 3. 최소 길이 확인 (완화)
    min_length = len(question.strip()) >= 3
    
    # 4. 시나리오 관련 구문 확인
    scenario_phrases = ["남자는", "남자가", "남자의", "열기구는", "열기구가", "성냥은", "성냥이", "사막은", "사막이"]
    is_scenario_related = any(phrase in q for phrase in scenario_phrases)
    
    # 5. 추리 관련 질문 패턴 (강화)
    import re
    # "~했나요?", "~있나요?", "~인가요?" 패턴
    if re.search(r'(.+)(했나요|있나요|인가요|했어요|있어요|인가요)', q):
        return True
    
    # "~와 관련이 있나요?" 패턴
    if re.search(r'(.+)\s*와\s*관련이\s*있나요', q):
        return True
    
    # "~을 사용했나요?" 패턴
    if re.search(r'(.+)\s*을\s*사용했나요', q):
        return True
    
    return has_scenario_keyword or (is_question_form and min_length) or is_scenario_related

def is_nonsense_pattern(question: str) -> bool:
    """무의미한 패턴 감지 (규칙 기반)"""
    q = question.strip().lower()
    
    # 1. 반복 문자 패턴 (골라골라돌려돌려돌림판)
    if len(q) > 10 and len(set(q)) < len(q) * 0.4:  # 중복 문자가 60% 이상
        return True
    
    # 2. 너무 짧은 무의미한 질문
    if len(q) <= 2:
        return True
    
    # 3. 특수문자나 숫자가 과도하게 많은 경우
    special_chars = sum(1 for c in q if not c.isalnum() and c not in "가-힣")
    if len(q) > 5 and special_chars > len(q) * 0.5:  # 특수문자가 50% 이상
        return True
    
    # 4. 한글 자음/모음이 섞여서 의미없는 조합
    if any(pattern in q for pattern in [
        "ㄷㅂㅈ료", "ㄷㅂㅈ료ㅗ", "ㄷㅂㅈ료ㅗㄹ", "ㄷㅂㅈ료ㅗㄹㄴ",
        "ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ", "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"
    ]):
        return True
    
    # 5. 반복되는 무의미한 단어 (패턴 기반)
    import re
    # 같은 단어가 3번 이상 반복되는 패턴
    if re.search(r'(.{2,})\1{2,}', q):  # 2글자 이상 단어가 3번 이상 반복
        return True
    
    # 6. 의미없는 조합 패턴 (규칙 기반)
    # "그 뭐" + "더라/냐/지/야" 패턴
    if re.search(r'그\s*뭐(더라|냐|지|야)', q):
        return True
    
    # "결국 아무것도" + "못하" 패턴
    if re.search(r'결국\s*아무것도\s*못하', q):
        return True
    
    # 7. 시나리오와 전혀 관련없는 키워드 (최소한만)
    unrelated_keywords = [
        "괴담", "공룡", "외계인", "마법", "시간여행", "차원", "포털",
        "유령", "귀신", "영혼", "저주", "좀비", "뱀파이어", "늑대인간", "드래곤",
        "중력", "자기장", "방사능", "핵폭탄", "미사일", "레이저", "플라즈마",
        "태풍", "허리케인", "사이클론", "토네이도", "회오리", "눈사태", "산사태",
        "지진", "해일", "쓰나미", "화산", "용암", "홍수", "가뭄", "폭설", "우박", "번개", "천둥",
        # 새로 추가된 무의미한 키워드들
        "갈매기", "고양이갈매기", "야옹야옹", "고양이", "새", "동물", "야옹",
        "밥맛", "꿀맛", "맛", "음식", "밥", "꿀", "맛있다", "맛없다",
        "시간", "멈출", "멈춰라", "마이 월드", "아톨", "체리", "멍멍이", "따따블", "펀치", "이얏"
    ]
    if any(keyword in q for keyword in unrelated_keywords):
        return True
    
    return False

def load_learned_overrides():
    """학습된 오버라이드 로드"""
    try:
        with open(LEARNED_OVERRIDES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_learned_overrides(overrides):
    """학습된 오버라이드 저장"""
    with open(LEARNED_OVERRIDES_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)

def load_answer_feedback():
    """정답 피드백 로드"""
    try:
        with open(ANSWER_FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_answer_feedback(feedback):
    """정답 피드백 저장"""
    with open(ANSWER_FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)

# 질문 분류기 클래스
class QuestionClassifier:
    @staticmethod
    def is_relevant_question(question: str) -> bool:
        """질문이 시나리오와 관련이 있는지 확인"""
        q = normalize_text(question)
        return any(keyword in q for keyword in DesertConstants.CORE_KEYWORDS)
    
    @staticmethod
    def is_nonsense_question(question: str) -> bool:
        """무의미한 질문인지 확인"""
        q = normalize_text(question)
        return any(pattern in q for pattern in DesertConstants.NONSENSE_PATTERNS)
    
    @staticmethod
    def is_wrong_answer_question(question: str) -> bool:
        """오답 질문인지 확인"""
        q = normalize_text(question)
        return any(pattern in q for pattern in DesertConstants.WRONG_ANSWER_PATTERNS)
    
    @staticmethod
    def is_off_scenario_question(question: str) -> bool:
        """시나리오와 관련 없는 질문인지 확인"""
        q = normalize_text(question)
        return any(banned in q for banned in DesertConstants.BANNED_OFF_SCENARIO)
    
    @staticmethod
    def is_physical_evidence_question(question: str) -> bool:
        """신체적 증거 관련 질문인지 확인"""
        q = normalize_text(question)
        return any(pattern in q for pattern in DesertConstants.PHYSICAL_EVIDENCE_QUESTIONS)

# 질문 판단기 클래스
class QuestionJudge:
    @staticmethod
    def check_learned_overrides(question: str) -> dict:
        """학습된 오버라이드 확인"""
        for override in LEARNED_OVERRIDES:
            if override["question"] == question:
                return {
                    "verdict": override["correct_classification"],
                    "evidence": "학습된 오버라이드",
                    "nl": override["correct_answer"]
                }
        return None
    
    @staticmethod
    def check_nonsense_question(question: str) -> dict:
        """무의미한 질문 확인"""
        if QuestionClassifier.is_nonsense_question(question):
            return {
                "verdict": "no",
                "evidence": "무의미한 질문",
                "nl": "아니오"
            }
        return None
    
    @staticmethod
    def check_wrong_answer_question(question: str) -> dict:
        """오답 질문 확인"""
        if QuestionClassifier.is_wrong_answer_question(question):
            return {
                "verdict": "no",
                "evidence": "오답 질문",
                "nl": "아니오"
            }
        return None
    
    @staticmethod
    def check_specific_rules(question: str) -> dict:
        """특정 규칙들 확인"""
        q = normalize_text(question)
        
        # 성냥 관련 규칙 - 제비뽑기 외의 용도는 모두 "아니오"
        if "성냥" in question:
            # 제비뽑기 관련이 아닌 성냥 용도들
            if any(word in q for word in [
                "주웠", "체온", "따뜻", "불", "불을", "환상", "소녀", "팔이", 
                "사용", "쓰", "피웠", "점화", "연기", "신호", "조명", "난방",
                "타고 난 이후", "타고 난 후", "타고 난 다음", "타고 난 뒤"
            ]):
                return {
                    "verdict": "no",
                    "evidence": "성냥 용도 규칙",
                    "nl": "아니오"
                }
            # 제비뽑기 관련만 "예"
            elif any(word in q for word in ["제비뽑기", "뽑", "추첨", "선택", "결정"]):
                return {
                    "verdict": "yes",
                    "evidence": "성냥 제비뽑기 규칙",
                    "nl": "예"
                }
            # 성냥 소지/보유 관련 질문은 "예"
            elif any(word in q for word in ["들고", "가지고", "소지", "보유", "있나", "있어", "있나요", "있어요"]):
                return {
                    "verdict": "yes",
                    "evidence": "성냥 소지 규칙",
                    "nl": "예"
                }
            # 성냥 상태 관련 질문은 "예" (부러진, 깨진 등)
            elif any(word in q for word in ["부러진", "부러졌", "깨진", "깨졌", "손상", "손상된", "상태"]):
                return {
                    "verdict": "yes",
                    "evidence": "성냥 상태 규칙",
                    "nl": "예"
                }
            # 성냥만 언급하고 구체적 용도가 없는 경우 "아니오"
            else:
                return {
                    "verdict": "no",
                    "evidence": "성냥 용도 불명확",
                    "nl": "아니오"
                }
        
        # 남자 상태 관련 규칙 (남자는 이미 죽었으므로)
        if any(word in q for word in ["서 있", "앉아 있", "일어나", "움직이", "걷", "뛰", "살아 있"]):
            return {
                "verdict": "no",
                "evidence": "남자 상태 규칙",
                "nl": "아니오"
            }
        # 죽은 사람은 누워 있는 상태
        elif any(word in q for word in ["누워 있", "누워있", "누워서"]):
            return {
                "verdict": "yes",
                "evidence": "남자 상태 규칙",
                "nl": "예"
            }
        
        # 옷을 벗은 이유 관련 규칙
        if "옷을 벗은 이유" in question or "옷을 벗은 건" in question:
            if any(word in q for word in ["더워서", "추워서", "그냥", "일행이", "낙타", "깃발", "신호"]):
                return {
                    "verdict": "no",
                    "evidence": "옷을 벗은 이유 규칙",
                    "nl": "아니오"
                }
        
        # 교통수단 관련 규칙
        if any(word in q for word in ["하마", "말", "자동차", "비행기", "배", "기차", "자전거", "오토바이"]):
            return {
                "verdict": "no",
                "evidence": "교통수단 규칙",
                "nl": "아니오"
            }
        
        return None

def handle_detailed_question(question: str) -> bool:
    """상세 질문 (어떻게, 왜, 무엇 등) 감지"""
    detailed_keywords = ["왜", "어떻게", "무엇", "누구", "언제", "어디서", "어떤", "몇", "얼마나"]
    result = any(keyword in question for keyword in detailed_keywords)
    print(f"DEBUG: handle_detailed_question('{question}') = {result}")
    return result

def is_scenario_external_question(question: str) -> bool:
    """시나리오에 없는 정보를 묻는 질문인지 확인"""
    external_keywords = [
        "나이", "직업", "가족", "친구", "학교", "회사", "주소", "전화번호",
        "생년월일", "혈액형", "키", "몸무게", "취미", "좋아하는", "싫어하는",
        "결혼", "아내", "남편", "자녀", "부모", "형제", "자매", "할아버지", "할머니",
        "학력", "학력", "전공", "졸업", "재학", "휴학", "중퇴", "졸업",
        "소득", "재산", "돈", "월급", "연봉", "부자", "가난", "빚",
        "종교", "신앙", "기독교", "불교", "천주교", "이슬람", "무신론",
        "정치", "투표", "정당", "대통령", "국회의원", "시장", "구청장",
        "운동", "축구", "야구", "농구", "테니스", "골프", "수영", "달리기",
        # 위치 관련 키워드 추가
        "정중앙", "중앙", "위치", "어디", "좌표", "경도", "위도", "방향", "북쪽", "남쪽", "동쪽", "서쪽",
        "거리", "미터", "킬로미터", "km", "m", "근처", "주변", "주위"
    ]
    
    q = normalize_text(question)
    return any(keyword in q for keyword in external_keywords)

def classify_question_type(question: str) -> str:
    """질문 유형 분류 (시나리오 기반 개선)"""
    # 1. 의미있는 질문인지 먼저 확인 (최우선)
    if is_meaningful_question(question):
        # 시나리오 외 정보 질문 확인
        if is_scenario_external_question(question):
            return "scenario_external"
        else:
            return "scenario_based"
    
    # 2. 무의미한 패턴 감지 (나중에)
    if is_nonsense_pattern(question):
        return "nonsense"
    
    # 3. 관련없는 질문
    return "irrelevant"

def classify_question_quality(question: str) -> str:
    """질문 품질 분류"""
    if is_nonsense_pattern(question):
        return "nonsense"
    elif not is_meaningful_question(question):
        return "irrelevant"
    elif is_meaningful_question(question):
        return "relevant"
    else:
        return "ambiguous"

def analyze_question_semantics(question: str) -> dict:
    """질문의 의미를 분석하여 가중치 기반 분류"""
    q = normalize_text(question)
    
    # 키워드 가중치 시스템
    keyword_weights = {
        # 핵심 키워드 (높은 가중치)
        "열기구": 10, "성냥": 10, "제비뽑기": 10, "남자": 8, "죽음": 8, "사막": 8,
        "사고": 6, "원인": 6, "왜": 5, "어떻게": 5, "무엇": 4, "누구": 4,
        
        # 관련 키워드 (중간 가중치)
        "뛰어내": 5, "떨어": 5, "추락": 5, "희생": 5, "일행": 4, "내려야": 4,
        "사망": 4, "부러진": 4, "손에": 3, "쥐고": 3,
        
        # 무의미한 키워드 (음수 가중치)
        "괴담": -10, "공룡": -10, "김갑환": -10, "매치스틱": -5, "트웬티": -5,
        "골라골라": -10, "정말로정말": -10, "간단한질문": -5
    }
    
    # 가중치 계산
    total_weight = 0
    matched_keywords = []
    
    for keyword, weight in keyword_weights.items():
        if keyword in q:
            total_weight += weight
            matched_keywords.append((keyword, weight))
    
    # 분류 기준
    if total_weight >= 15:
        return {"quality": "excellent", "weight": total_weight, "keywords": matched_keywords}
    elif total_weight >= 8:
        return {"quality": "good", "weight": total_weight, "keywords": matched_keywords}
    elif total_weight >= 0:
        return {"quality": "fair", "weight": total_weight, "keywords": matched_keywords}
    else:
        return {"quality": "poor", "weight": total_weight, "keywords": matched_keywords}

def judge_question_cached(question: str) -> dict:
    """캐시를 사용한 질문 판단 (최적화된 LRU + 에러 처리)"""
    global _question_cache, _performance_stats
    
    try:
        _performance_stats["total_questions"] += 1
        
        # 입력 검증
        if not question or not isinstance(question, str):
            return {"verdict": "no", "evidence": "입력 오류", "nl": "올바른 질문을 입력해주세요."}
        
        # 캐시 확인 (OrderedDict로 O(1) 접근)
        cache_key = question.strip().lower()
        if cache_key in _question_cache:
            _performance_stats["cache_hits"] += 1
            # LRU: 접근한 항목을 맨 뒤로 이동 (O(1) 연산)
            _question_cache.move_to_end(cache_key)
            return _question_cache[cache_key]
        
        # 캐시에 없으면 계산
        _performance_stats["cache_misses"] += 1
        result = judge_question(question)
        
        # 결과 검증
        if not result or not isinstance(result, dict):
            return {"verdict": "no", "evidence": "처리 오류", "nl": "죄송합니다. 다시 시도해주세요."}
        
        # 캐시 크기 관리 (최적화된 버전)
        if len(_question_cache) >= _cache_max_size:
            # 가장 오래된 항목 삭제 (O(1) 연산)
            _question_cache.popitem(last=False)
            _performance_stats["cache_evictions"] += 1
        
        # 캐시 저장
        _question_cache[cache_key] = result
        
        return result
        
    except Exception as e:
        # 에러 로깅
        logger.error(f"Error in judge_question_cached: {e}")
        return {"verdict": "no", "evidence": "시스템 오류", "nl": "죄송합니다. 다시 시도해주세요."}

def get_memory_usage():
    """메모리 사용량 모니터링"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss": memory_info.rss / 1024 / 1024,  # MB
            "vms": memory_info.vms / 1024 / 1024,  # MB
            "cache_size": len(_question_cache),
            "cache_memory_estimate": len(_question_cache) * 0.5  # KB per entry estimate
        }
    except ImportError:
        return {
            "rss": 0,
            "vms": 0,
            "cache_size": len(_question_cache),
            "cache_memory_estimate": len(_question_cache) * 0.5
        }

def get_performance_stats() -> dict:
    """성능 통계 반환 (메모리 정보 포함)"""
    global _performance_stats
    total = _performance_stats["total_questions"]
    if total > 0:
        hit_rate = _performance_stats["cache_hits"] / total * 100
        memory_info = get_memory_usage()
        return {
            **_performance_stats,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(_question_cache),
            "memory_efficiency": f"{len(_question_cache)}/{_cache_max_size}",
            "memory_usage": memory_info
        }
    return _performance_stats

def quick_filter_checks(question: str) -> dict:
    """빠른 필터링 검사들"""
    # 1. 무의미한 패턴 감지
    if is_nonsense_pattern(question):
        return {"verdict": "no", "evidence": "무의미한 질문", "nl": "추리와 연관있는 질문이 아닙니다."}
    
    # 2. 의미있는 질문인지 빠른 검사
    if not is_meaningful_question(question):
        return {"verdict": "no", "evidence": "관련없는 질문", "nl": "이 사건과 관련된 질문을 해주세요."}
    
    return None

def detailed_question_analysis(question: str) -> dict:
    """상세한 질문 분석 (중복 제거됨)"""
    # 1. 학습된 오버라이드 확인
    override_result = QuestionJudge.check_learned_overrides(question)
    if override_result:
        return override_result
    
    # 2. 오답 질문 확인 (무의미한 질문은 이미 quick_filter_checks에서 처리됨)
    wrong_answer_result = QuestionJudge.check_wrong_answer_question(question)
    if wrong_answer_result:
        return wrong_answer_result
    
    return None

def judge_question(question: str) -> dict:
    """질문을 판단하여 답변을 생성 (체계적 분류 시스템)"""
    
    # 🔍 1단계: 기본 필터링 (가장 빠른 검사들)
    # 1-1. 무의미한 패턴 감지 (최우선)
    if is_nonsense_pattern(question):
        return {"verdict": "no", "evidence": "무의미한 질문", "nl": "추리와 연관있는 질문이 아닙니다."}
    
    # 1-2. 시나리오 외부 질문 감지
    if is_scenario_external_question(question):
        return {"verdict": "no", "evidence": "시나리오 외 정보", "nl": "이 정보는 시나리오에 포함되어 있지 않습니다. 사건과 관련된 질문을 해보세요."}
    
    # 1-3. 의미있는 질문인지 빠른 검사
    if not is_meaningful_question(question):
        return {"verdict": "no", "evidence": "관련없는 질문", "nl": "이 사건과 관련된 질문을 해주세요."}
    
    # 🔍 2단계: 학습된 규칙 적용 (우선순위 높음)
    # 2-1. 학습된 오버라이드 확인
    override_result = QuestionJudge.check_learned_overrides(question)
    if override_result:
        return override_result
    
    # 2-2. 오답 질문 확인
    wrong_answer_result = QuestionJudge.check_wrong_answer_question(question)
    if wrong_answer_result:
        return wrong_answer_result
    
    # 🔍 3단계: 특정 규칙들 확인 (시나리오 기반)
    # 3-1. 성냥 관련 특별 규칙
    specific_rules_result = QuestionJudge.check_specific_rules(question)
    if specific_rules_result:
        return specific_rules_result
    
    # 🚰 4단계: 신체적 증거 관련 질문 확인 (완전 안전한 필터링)
    if QuestionClassifier.is_physical_evidence_question(question):
        q = normalize_text(question)
        
        # 🚨 위험한 키워드 즉시 차단 (최우선)
        dangerous_keywords = ["간", "폐", "심장", "신장", "비장", "위", "장", "출혈", "뇌출혈", "내출혈", "뇌 내출혈"]
        if any(keyword in q for keyword in dangerous_keywords):
            return {"verdict": "no", "evidence": "시나리오 무관", "nl": "이 정보는 시나리오에 포함되어 있지 않습니다. 사건과 관련된 질문을 해보세요."}
        
        # 🚨 시나리오와 무관한 신체적 증거 차단
        irrelevant_physical = ["간이", "폐가", "심장이", "신장이", "비장이", "위가", "장이"]
        if any(keyword in q for keyword in irrelevant_physical):
            return {"verdict": "no", "evidence": "시나리오 무관", "nl": "이 정보는 시나리오에 포함되어 있지 않습니다. 사건과 관련된 질문을 해보세요."}
        
        # ✅ 안전한 신체적 증거만 처리 (떨어져서 생긴 상처/부상)
        if any(word in q for word in ["상처가 없", "깨끗", "정상", "다치지 않", "부상이 없", "손상이 없", "건강", "무사"]):
            return {"verdict": "no", "evidence": "신체적 증거", "nl": "아니오"}
        else:
            # 시나리오와 관련된 상처/부상만 "예" 처리
            if any(word in q for word in ["상처", "다쳤", "부상", "손상", "멍", "부어", "변형", "절단"]):
                return {"verdict": "yes", "evidence": "신체적 증거", "nl": "예"}
            else:
                return {"verdict": "no", "evidence": "시나리오 무관", "nl": "이 정보는 시나리오에 포함되어 있지 않습니다. 사건과 관련된 질문을 해보세요."}
    
    # 🔍 5단계: 상세 질문 유형 분류 (최종 분류)
    question_type = classify_question_type(question)
    
    # 5-1. 상세 질문 처리 (어떻게, 왜, 무엇 등)
    if handle_detailed_question(question):
        return {"verdict": "no", "evidence": "상세 질문", "nl": "예/아니오로 답변할 수 있는 질문만 해달라"}
    
    # 5-2. 시나리오 기반 질문
    if question_type == "scenario_based":
        return {"verdict": "yes", "evidence": "시나리오 기반", "nl": "예"}
    
    # 5-3. 기타 유형들
    if question_type == "wrong_answer":
        return {"verdict": "no", "evidence": "오답 질문", "nl": "아니오"}
    elif question_type == "off_scenario":
        return {"verdict": "no", "evidence": "시나리오 무관", "nl": "아니오"}
    else:
        return {"verdict": "no", "evidence": "애매한 질문", "nl": "아니오"}
    
    # 🔍 6단계: 부정의문문 처리 (최종 단계)
    # result 변수가 정의되지 않았으므로 기본값 설정
    result = {"verdict": "no", "evidence": "애매한 질문", "nl": "아니오"}
    
    is_negative = is_negative_question(question)
    if is_negative:
        if result["verdict"] == "yes":
            result["verdict"] = "no"
            result["nl"] = "아니오"
        elif result["verdict"] == "no":
            result["verdict"] = "yes"
            result["nl"] = "예"
    
    return result

# Flask 라우트들
@app.route('/')
def index():
    return render_template('index.html', scenario=SCENARIO)

@app.route('/ask', methods=['POST'])
def ask():
    init_session()
    question = request.json.get('question', '').strip()
    if not question:
        logger.warning("Empty question received")
        return jsonify({'error': '질문을 입력해주세요.'}), 400
    
    logger.info(f"Processing question: {question[:50]}...")
    result = judge_question_cached(question)
    
    # JavaScript가 기대하는 형식으로 변환
    if result['verdict'] == 'yes':
        answer_text = '예'
    elif result['verdict'] == 'no':
        answer_text = '아니오'
    elif result['verdict'] == 'ambiguous':
        answer_text = '판단이 애매하거나 문제 풀이와 연관이 없거나 사실이 아닙니다'
    elif result['verdict'] == 'nonsense':
        answer_text = '그런 질문은 이 사건과 전혀 관련이 없습니다'
    else:
        answer_text = result['verdict']

    # 토큰 소모 (질문할 때마다 토큰 1개 소모)
    tokens_left = session.get('tokens_left', 20)
    if tokens_left > 0:
        session['tokens_left'] = tokens_left - 1
    
    return jsonify({
        'result': result['verdict'],
        'answerText': answer_text,
        'evidence': result.get('evidence', ''),
        'nl': result.get('nl', answer_text),
        'tokensLeft': session.get('tokens_left', 20)
    })

@app.route('/hint', methods=['POST'])
def hint():
    init_session()
    # 힌트 요청 처리
    hints = SCENARIO.get('hints', [])
    used_hints = session.get('used_hints', [])
    
    if len(used_hints) >= len(hints):
        return jsonify({'error': '더 이상 힌트가 없습니다.'}), 400
    
    # 다음 힌트 가져오기
    hint_text = hints[len(used_hints)]
    used_hints.append(hint_text)
    session['used_hints'] = used_hints
    
    # 힌트는 토큰(질문 횟수)을 소모하지 않음
    # 힌트 횟수만 차감됨
    
    return jsonify({
        'hint': hint_text,
        'hints_left': len(hints) - len(used_hints),
        'tokens_left': session.get('tokens_left', 20)  # 토큰은 그대로 유지
    })

@app.route('/guess', methods=['POST'])
def guess():
    init_session()
    guess_text = request.json.get('guess', '').strip()
    if not guess_text:
        return jsonify({'error': '정답을 입력해주세요.'}), 400
    
    # 핵심 키워드들 (모두 포함되어야 함)
    anchor_all = {"열기구", "성냥", "제비뽑기", "내기"}
    anchor_any = {"뛰어내", "떨어", "추락", "희생", "일행", "내려야", "사망"}
    
    # 정답 패턴들 (간소화)
    core_combinations = [
        "열기구 하강 제비뽑기 희생",
        "성냥 제비뽑기 뛰어내려",
        "열기구 추락 제비뽑기",
        "성냥으로 제비뽑기 희생",
        "열기구 무게 제비뽑기",
        "성냥 뽑아 희생",
        "열기구에서 뛰어내려",
        "제비뽑기로 희생자 결정",
        "부러진 성냥 뽑아",
        "열기구 하강 막기 위해",
        "일행과 열기구",
        "열기구에서 한 명이 내려야",
        "희생자로 뽑혀",
        "열기구에서 내려야 하는 상황",
        "모종의 이유로 열기구에서",
        "한 명이 내려야 하는 상황이 발생",
        "성냥을 통한 내기",
        "성냥 내기로",
        "내기로 희생자",
        "성냥으로 내기",
        "열기구에서 내기로"
    ]
    
    # 필수 조합들
    essential_combinations = [
        "열기구 제비뽑기",
        "열기구 내기",
        "성냥 희생",
        "성냥 내기",
        "뛰어내려 죽",
        "열기구 일행",
        "열기구에서 내려야",
        "희생자로 뽑혀",
        "열기구에서 한 명이"
    ]
    
    # 오답 패턴들
    wrong_answer_patterns = [
        "낙타", "선인장", "길을 잃", "물이 없", "더위", "추위",
        "하마", "말", "자동차", "비행기", "배", "기차",
        "깃발", "신호", "구조", "타인이", "스스로"
    ]
    
    # 점수 계산
    guess_lower = normalize_text(guess_text)
    
    # 핵심 키워드 확인 (더 엄격한 기준)
    # 필수: 열기구 + 성냥 + (제비뽑기 또는 내기) + (뛰어내거나 희생 관련)
    has_essential = (
        "열기구" in guess_lower and 
        "성냥" in guess_lower and 
        ("제비뽑기" in guess_lower or "내기" in guess_lower) and
        any(word in guess_lower for word in ["뛰어내", "떨어", "추락", "희생", "뽑혀", "사망"])
    )
    
    # 기존 방식도 유지하되 더 엄격하게
    has_all = all(keyword in guess_lower for keyword in anchor_all)
    has_any = any(keyword in guess_lower for keyword in anchor_any)
    
    # 핵심 조합 확인
    has_core_combination = any(combo in guess_lower for combo in core_combinations)
    has_essential_combination = any(combo in guess_lower for combo in essential_combinations)
    
    # 오답 패턴 확인
    has_wrong_pattern = any(pattern in guess_lower for pattern in wrong_answer_patterns)
    
    # 유사도 점수 계산
    score_pct = 0
    if has_all:
        score_pct += 40
    if has_any:
        score_pct += 30
    if has_core_combination:
        score_pct += 50
    if has_essential_combination:
        score_pct += 60
    
    # 정답 여부 판단 (더 엄격한 기준)
    is_correct = (
        not has_wrong_pattern and (
            # 필수 조건: 열기구 + 성냥 + 제비뽑기/내기 + 희생/뛰어내림
            has_essential or
            # 또는 기존 조건들 (더 엄격하게)
            (score_pct >= 70 and has_all and has_any) or
            (has_core_combination and score_pct >= 60) or
            (has_essential_combination and score_pct >= 50) or
            (score_pct >= 80 and has_any)
        )
    )
    
    return jsonify({
        'correct': is_correct,
        'has_all': has_all,
        'has_any': has_any,
        'has_core_combination': has_core_combination,
        'has_essential_combination': has_essential_combination,
        'has_wrong_pattern': has_wrong_pattern
    })

@app.route('/state', methods=['GET'])
def state():
    init_session()
    hints = SCENARIO.get('hints', [])
    used_hints = session.get('used_hints', [])
    
    return jsonify({
        'tokens_left': session.get('tokens_left', 20),
        'hints_left': len(hints) - len(used_hints),
        'used_hints': used_hints
    })

@app.route('/reset', methods=['POST'])
def reset():
    """게임 상태 초기화"""
    session.clear()
    session['tokens_left'] = 20
    session['used_hints'] = []
    
    return jsonify({
        'tokens_left': 20,
        'hints_left': 3,
        'message': '게임이 초기화되었습니다.'
    })

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    question = data.get('question', '').strip()
    verdict = data.get('verdict', '').strip()
    evidence = data.get('evidence', '').strip()
    nl = data.get('nl', '').strip()
    
    if not question or not verdict:
        return jsonify({'error': '질문과 판정을 입력해주세요.'}), 400
    
    # 새로운 오버라이드 추가
    new_override = {
        "question": question,
        "correct_answer": nl,
        "original_answer": verdict,
        "correct_classification": verdict,
        "timestamp": datetime.now().isoformat()
    }
    
    # 기존 오버라이드에 추가
    LEARNED_OVERRIDES.append(new_override)
    save_learned_overrides(LEARNED_OVERRIDES)
    
    return jsonify({'success': True, 'message': '피드백이 저장되었습니다.'})

@app.route('/answer_feedback', methods=['POST'])
def answer_feedback():
    data = request.json
    guess = data.get('guess', '').strip()
    is_correct = data.get('is_correct', False)
    comment = data.get('comment', '').strip()
    
    if not guess:
        return jsonify({'error': '정답을 입력해주세요.'}), 400
    
    # 새로운 피드백 추가
    new_feedback = {
        "guess": guess,
        "is_correct": is_correct,
        "comment": comment,
        "timestamp": datetime.now().isoformat()
    }
    
    # 기존 피드백에 추가
    ANSWER_FEEDBACK.append(new_feedback)
    save_answer_feedback(ANSWER_FEEDBACK)
    
    return jsonify({'success': True, 'message': '정답 피드백이 저장되었습니다.'})

@app.route('/reveal')
def reveal():
    return jsonify({
        'answer': '남자가 한 명의 일행과 함께 열기구를 타고 사막을 횡단하는 여행 도중, 모종의 이유로 열기구가 고장나는 사고가 발생했다.\n이에 무거운 짐을 버리고 옷까지 벗어 최대한 무게를 줄였지만, 열기구의 하강은 멈추지 않았다.\n이대로는 사막 한 가운데에서 둘 다 조난을 당할 위기였으므로 남자와 일행은 제비뽑기를 통해 열기구에서 내릴 희생자를 결정했다.\n남자는 불행하게도 부러진 성냥. 제비를 뽑았고, 스스로 열기구 밖으로 몸을 던져 사망했다.',
        'explanation': '이것이 사막의 남자 미스터리의 정답입니다.'
    })

@app.route('/stats')
def stats():
    """성능 통계 확인"""
    return jsonify(get_performance_stats())

if __name__ == '__main__':
    print("사막의 남자 챗봇 서버를 시작합니다...")
    print("브라우저에서 http://127.0.0.1:5000 으로 접속하세요.")
    app.run(debug=True, host='127.0.0.1', port=5000)
