@echo off
echo 사막 시나리오 챗봇 설치를 시작합니다...
echo.

echo Python 버전 확인 중...
python --version
if errorlevel 1 (
    echo Python이 설치되지 않았습니다. Python 3.7 이상을 설치해주세요.
    pause
    exit /b 1
)

echo.
echo 필요한 패키지를 설치합니다...
pip install flask>=2.3.0
pip install requests>=2.31.0

echo.
echo 설치가 완료되었습니다!
echo.
echo 실행 방법:
echo 1. desert 폴더로 이동: cd desert
echo 2. 서버 실행: python app_desert.py
echo 3. 브라우저에서 http://127.0.0.1:5000 접속
echo.
pause

