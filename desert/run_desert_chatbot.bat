@echo off
echo 사막 시나리오 챗봇을 시작합니다...
echo.

REM Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo Python이 설치되지 않았습니다!
    echo https://python.org 에서 Python을 설치해주세요.
    pause
    exit /b 1
)

REM 필요한 패키지 설치 (이미 설치된 경우 무시)
echo 필요한 패키지를 확인합니다...
pip install flask requests >nul 2>&1

REM 서버 실행
echo.
echo 서버를 시작합니다...
echo 브라우저에서 http://127.0.0.1:5000 으로 접속하세요.
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo.

python app_desert.py

