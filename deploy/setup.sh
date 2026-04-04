#!/bin/bash
# Oracle Cloud ARM Ubuntu 22.04 초기 세팅 스크립트
# 사용법: sudo bash setup.sh <GitHub_레포_URL> <ANTHROPIC_API_KEY> <COLLECT_SECRET>
#
# 예시:
#   sudo bash setup.sh https://github.com/yourname/da_job_archive sk-ant-xxx mysecret123

set -e

REPO_URL="$1"
ANTHROPIC_API_KEY="$2"
COLLECT_SECRET="$3"
APP_DIR="/opt/da_job_archive"
SERVICE_USER="ubuntu"

if [ -z "$REPO_URL" ] || [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$COLLECT_SECRET" ]; then
  echo "사용법: sudo bash setup.sh <GitHub_레포_URL> <ANTHROPIC_API_KEY> <COLLECT_SECRET>"
  exit 1
fi

echo "=== 1. 패키지 업데이트 ==="
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git nginx curl

echo "=== 2. 레포 클론 ==="
if [ -d "$APP_DIR" ]; then
  echo "디렉토리 존재 → git pull"
  cd "$APP_DIR" && git pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

echo "=== 3. Python 가상환경 및 패키지 설치 ==="
cd "$APP_DIR"
sudo -u "$SERVICE_USER" python3 -m venv venv
sudo -u "$SERVICE_USER" venv/bin/pip install --upgrade pip -q
sudo -u "$SERVICE_USER" venv/bin/pip install -r requirements.txt -q

echo "=== 4. Playwright Chromium 설치 ==="
sudo -u "$SERVICE_USER" venv/bin/playwright install chromium --with-deps

echo "=== 5. .env 파일 생성 ==="
cat > "$APP_DIR/.env" <<EOF
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
COLLECT_SECRET=$COLLECT_SECRET
DB_PATH=$APP_DIR/jobs.db
PORT=8000
EOF
chown "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

echo "=== 6. systemd 서비스 등록 ==="
cp "$APP_DIR/deploy/da-job-archive.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable da-job-archive
systemctl restart da-job-archive

echo "=== 7. nginx 설정 ==="
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/da-job-archive
ln -sf /etc/nginx/sites-available/da-job-archive /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== 8. 방화벽 설정 (iptables) ==="
# Oracle Cloud VM은 iptables가 기본 활성화되어 있음
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
# 재부팅 후에도 유지
apt install -y iptables-persistent
netfilter-persistent save

echo ""
echo "=== 완료 ==="
echo "서비스 상태: systemctl status da-job-archive"
echo "로그 확인:   journalctl -u da-job-archive -f"
echo ""
echo "⚠️  Oracle 콘솔에서도 포트 80/443 열어야 합니다:"
echo "   Networking → Virtual Cloud Networks → Security Lists → Ingress Rules 추가"
