import json
import re
import difflib
import time
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

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
app.secret_key = "dev-secret-key"

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
        "강요해서", "강제로", "강제하여", "강제해서", "불을 피우", "불을 피워",
        "불을 피우려", "불을 피우려다", "사고로", "사고가", "놀다가", "놀면서", "놀고",
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
                "verdict": "nonsense",
                "evidence": "무의미한 질문",
                "nl": "그런 질문은 이 사건과 전혀 관련이 없습니다. 사막의 남자와 부러진 성냥 사건에 집중해주세요."
            }
        return None
    
    @staticmethod
    def check_wrong_answer_question(question: str) -> dict:
        """오답 질문 확인"""
        if QuestionClassifier.is_wrong_answer_question(question):
            return {
                "verdict": "no",
                "evidence": "오답 질문",
                "nl": "아니요, 그렇지 않습니다."
            }
        return None
    
    @staticmethod
    def check_specific_rules(question: str) -> dict:
        """특정 규칙들 확인"""
        q = normalize_text(question)
        
        # 옷을 벗은 이유 관련 규칙
        if "옷을 벗은 이유" in question or "옷을 벗은 건" in question:
            if any(word in q for word in ["더워서", "추워서", "그냥", "일행이", "낙타", "깃발", "신호"]):
                return {
                    "verdict": "no",
                    "evidence": "옷을 벗은 이유 규칙",
                    "nl": "아니요, 남자가 옷을 벗은 이유는 무게를 줄이기 위해서입니다."
                }
        
        # 교통수단 관련 규칙
        if any(word in q for word in ["하마", "말", "자동차", "비행기", "배", "기차", "자전거", "오토바이"]):
            return {
                "verdict": "no",
                "evidence": "교통수단 규칙",
                "nl": "아니요, 남자는 열기구를 타고 여행했습니다."
            }
        
        return None

def classify_question_type(question: str) -> str:
    """질문 유형 분류"""
    if QuestionClassifier.is_nonsense_question(question):
        return "nonsense"
    elif QuestionClassifier.is_wrong_answer_question(question):
        return "wrong_answer"
    elif QuestionClassifier.is_off_scenario_question(question):
        return "off_scenario"
    elif QuestionClassifier.is_physical_evidence_question(question):
        return "physical_evidence"
    elif QuestionClassifier.is_relevant_question(question):
        return "scenario_based"
    else:
        return "ambiguous"

def judge_question(question: str) -> dict:
    """질문을 판단하여 답변을 생성"""
    q = normalize_text(question)

    # 1. 학습된 오버라이드 확인 (최고 우선순위)
    override_result = QuestionJudge.check_learned_overrides(question)
    if override_result:
        return override_result

    # 2. 무의미한 질문 확인
    nonsense_result = QuestionJudge.check_nonsense_question(question)
    if nonsense_result:
        return nonsense_result
    
    # 3. 오답 질문 확인
    wrong_answer_result = QuestionJudge.check_wrong_answer_question(question)
    if wrong_answer_result:
        return wrong_answer_result
    
    # 4. 신체적 증거 관련 질문 확인
    if QuestionClassifier.is_physical_evidence_question(question):
        # 상처/부상 관련은 "예", 깨끗/정상 관련은 "아니오"
        q = normalize_text(question)
        if any(word in q for word in ["상처가 없", "깨끗", "정상", "다치지 않", "부상이 없", "손상이 없", "건강", "무사"]):
            return {"verdict": "no", "evidence": "신체적 증거", "nl": "아니요, 높은 곳에서 떨어져 죽었으므로 상처가 있고 몸이 다쳐있습니다."}
        else:
            return {"verdict": "yes", "evidence": "신체적 증거", "nl": "예, 맞습니다."}
    
    # 5. 특정 규칙들 확인
    specific_rules_result = QuestionJudge.check_specific_rules(question)
    if specific_rules_result:
        return specific_rules_result
    
    # 6. 질문 유형 분류
    question_type = classify_question_type(question)
    
    # 7. 유형별 처리
    if question_type == "nonsense":
        return {"verdict": "nonsense", "evidence": "", "nl": "그런 질문은 이 사건과 전혀 관련이 없습니다. 사막의 남자와 부러진 성냥 사건에 집중해주세요."}
    elif question_type == "wrong_answer":
        return {"verdict": "no", "evidence": "", "nl": "아니요, 그렇지 않습니다."}
    elif question_type == "off_scenario":
        return {"verdict": "ambiguous", "evidence": "", "nl": "그런 질문은 이 사건과 관련이 없습니다. 사막의 남자와 부러진 성냥 사건에 집중해주세요."}
    elif question_type == "scenario_based":
        return {"verdict": "yes", "evidence": "시나리오 기반", "nl": "예, 맞습니다."}
    else:
        return {"verdict": "ambiguous", "evidence": "", "nl": "판단이 애매하거나 문제 풀이와 연관이 없거나 사실이 아닙니다."}

# Flask 라우트들
@app.route('/')
def index():
    return render_template('index.html', scenario=SCENARIO)

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question', '').strip()
    if not question:
        return jsonify({'error': '질문을 입력해주세요.'}), 400
    
    result = judge_question(question)
    
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

    return jsonify({
        'result': result['verdict'],
        'answerText': answer_text,
        'evidence': result.get('evidence', ''),
        'nl': result.get('nl', answer_text),
        'tokensLeft': 20  # 고정값
    })

@app.route('/guess', methods=['POST'])
def guess():
    guess_text = request.json.get('guess', '').strip()
    if not guess_text:
        return jsonify({'error': '정답을 입력해주세요.'}), 400
    
    # 핵심 키워드들
    anchor_all = {"열기구", "성냥", "제비뽑기"}
    anchor_any = {"뛰어내", "떨어", "추락", "희생"}
    
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
        "열기구 하강 막기 위해"
    ]
    
    # 필수 조합들
    essential_combinations = [
        "열기구 제비뽑기",
        "성냥 희생",
        "뛰어내려 죽"
    ]
    
    # 오답 패턴들
    wrong_answer_patterns = [
        "낙타", "선인장", "길을 잃", "물이 없", "더위", "추위",
        "하마", "말", "자동차", "비행기", "배", "기차",
        "깃발", "신호", "구조", "타인이", "스스로"
    ]
    
    # 점수 계산
    guess_lower = normalize_text(guess_text)
    
    # 핵심 키워드 확인
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
    
    # 정답 여부 판단
    is_correct = (
        not has_wrong_pattern and (
            (score_pct >= 60 and has_all and (has_any or has_core_combination)) or
            (has_core_combination and score_pct >= 50) or
            (has_essential_combination and score_pct >= 40) or
            (score_pct >= 70 and has_any) or
            (score_pct >= 80)
        )
    )
    
    return jsonify({
        'correct': is_correct,
        'score': score_pct,
        'has_all': has_all,
        'has_any': has_any,
        'has_core_combination': has_core_combination,
        'has_essential_combination': has_essential_combination,
        'has_wrong_pattern': has_wrong_pattern
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
        'answer': '남자는 열기구에서 하강하는 위기 상황에서, 성냥으로 제비뽑기를 하여 희생자가 되었습니다. 부러진 성냥을 뽑은 남자는 열기구에서 뛰어내려 사망했습니다.',
        'explanation': '이것이 사막의 남자 미스터리의 정답입니다.'
    })

if __name__ == '__main__':
    print("사막의 남자 챗봇 서버를 시작합니다...")
    print("브라우저에서 http://127.0.0.1:5000 으로 접속하세요.")
    app.run(debug=True, host='127.0.0.1', port=5000)