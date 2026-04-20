#!/bin/bash
# dicto インストーラー
# curl -fsSL https://ykshio.github.io/dicto/install.sh | bash

set -e

echo "=================================================="
echo " dicto - 文字起こしアプリ インストーラー"
echo "=================================================="
echo ""

# --- インストール先 ---
INSTALL_DIR="$HOME/dicto"

if [ -d "$INSTALL_DIR" ]; then
    echo "既存のインストールが見つかりました。更新します。"
    echo ""
fi

# --- Homebrewの確認 ---
if ! command -v brew &> /dev/null; then
    echo "[1/5] Homebrewをインストールします..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "[1/5] Homebrew ✓"
fi

# --- Python と ffmpeg ---
echo "[2/5] Python と ffmpeg をインストール中..."
brew install python@3.11 ffmpeg 2>/dev/null || true

# --- ソースコードのダウンロード ---
echo "[3/5] dicto をダウンロード中..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --ff-only origin main
else
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/ykshio/dicto.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# --- Python仮想環境 ---
echo "[4/5] Python環境をセットアップ中..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install faster-whisper gradio -q

# --- .appの生成 ---
echo "[5/5] アプリを生成中..."
APP_DIR="/Applications/dicto.app"
rm -rf "$APP_DIR"
cp -R app_template "$APP_DIR"
echo "$INSTALL_DIR" > "$APP_DIR/Contents/Resources/install_path.txt"

echo ""
echo "=================================================="
echo " インストール完了! 🎉"
echo "=================================================="
echo ""
echo "Launchpad または /Applications から"
echo "「dicto」アプリを起動してください。"
echo ""
echo "※ 初回起動時に「開発元が未確認」と出たら:"
echo "   右クリック → 「開く」で起動できます。"
echo ""
