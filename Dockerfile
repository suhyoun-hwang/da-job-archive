FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저는 베이스 이미지에 이미 포함되어 있지만
# Python 패키지와 연결을 위해 재등록
RUN playwright install chromium

COPY . .

CMD sh -c "gunicorn app:app --bind 0.0.0.0:${PORT:-5001} --workers 1 --timeout 120"
