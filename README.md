# Desert Mystery Chatbot

사막 미스터리 챗봇 - 추리 게임

## 시나리오
"알몸의 남자가 사막 한 가운데에서 죽어있었다. 그의 손에는 부러진 성냥이 들려있었다. 왜 그는 사막 한 가운데에서 죽어있었을까?"

## 설치 및 실행

### 1. Python 설치
Python 3.7 이상이 필요합니다.

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 실행
```bash
cd desert
python app_desert.py
```

또는 배치 파일 사용:
```bash
desert/run_desert_chatbot.bat
```

### 4. 웹 브라우저에서 접속
http://127.0.0.1:5000

## 게임 방법
1. 웹 인터페이스에서 질문을 입력하세요
2. 챗봇이 "예", "아니오", "판단이 애매합니다" 등으로 답변합니다
3. 힌트 버튼을 눌러 도움을 받을 수 있습니다
4. 정답을 맞추면 게임이 끝납니다

## 정답
남자는 낙하산을 타고 있었는데, 낙하산이 고장나서 떨어져 죽었습니다. 부러진 성냥은 낙하산의 줄을 자르려고 했던 흔적입니다.

## 파일 구조
```
desert/
├── app_desert.py          # 메인 Flask 애플리케이션
├── templates/
│   └── index.html         # 웹 인터페이스
├── learned_overrides.json # 학습된 답변 오버라이드
└── desert_match.json      # 시나리오 데이터
```

## 기능
- 질문 분류 및 답변 생성
- 학습된 답변 오버라이드 시스템
- 웹 기반 사용자 인터페이스
- 힌트 및 정답 공개 기능