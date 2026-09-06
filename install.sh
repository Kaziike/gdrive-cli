#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/gdrive"

echo "==> Cài đặt gdrive-cli tại $PROJECT_DIR..."

# 1. Tạo venv nếu chưa có
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "==> Đang khởi tạo môi trường ảo Python venv..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# 2. Cài đặt các thư viện cần thiết
echo "==> Đang cài đặt thư viện..."
"$PROJECT_DIR/venv/bin/pip" install --quiet --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install --quiet -e "$PROJECT_DIR"

# 3. Tạo thư mục bin
mkdir -p "$BIN_DIR"

# 4. Tạo wrapper script gdrive
echo "==> Tạo lệnh gdrive tại $LAUNCHER..."
cat << 'EOF' > "$LAUNCHER"
#!/usr/bin/env bash
# Wrapper launcher for gdrive-cli
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.gemini/antigravity/scratch/gdrive-cli" 2>/dev/null && pwd)"
if [ ! -d "$PROJECT_DIR" ]; then
    PROJECT_DIR="/home/kaz/ProjectLinux/gdrive-cli"
fi
exec "$PROJECT_DIR/venv/bin/python3" -m gdrive_cli.cli "$@"
EOF

chmod +x "$LAUNCHER"

echo ""
echo "🎉 Cài đặt hoàn tất!"
echo "Bạn có thể sử dụng lệnh 'gdrive' ngay từ bất kỳ đâu trong terminal."
echo "Chạy thử: gdrive --help"
