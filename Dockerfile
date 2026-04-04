FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PORT 환경변수를 올바르게 확장하는 시작 스크립트
RUN printf '#!/bin/sh\nexec gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120\n' \
    > /start.sh && chmod +x /start.sh

EXPOSE 8080
CMD ["/start.sh"]
