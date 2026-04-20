#!/bin/bash
# Whisper文字起こしアプリ インストーラー (macOS用)

set -e

# スクリプトのあるディレクトリに移動
cd "$(dirname "$0")"

echo "=================================================="
echo " Whisper文字起こしアプリ セットアップ"
echo "=================================================="
echo ""
echo "このインストールには10〜20分ほどかかります。"
echo "途中でパスワードを求められたら、Macのログインパスワードを入力してください。"
echo ""
read -p "Enterキーを押して開始..."

# --- Homebrewの確認 ---
if ! command -v brew &> /dev/null; then
    echo ""
    echo "[1/4] Homebrewをインストールします..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Apple Silicon Mac向けのPATH設定
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo ""
    echo "[1/4] Homebrewは既にインストール済みです ✓"
fi

# --- Python と ffmpegのインストール ---
echo ""
echo "[2/4] Python と ffmpeg をインストールします..."
brew install python@3.11 ffmpeg || true

# --- 仮想環境の作成 ---
echo ""
echo "[3/4] Python仮想環境を作成します..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

# --- Pythonパッケージのインストール ---
echo ""
echo "[4/4] 必要なPythonパッケージをインストールします..."
echo "(モデルのダウンロードで時間がかかります)"
source venv/bin/activate
pip install --upgrade pip
pip install faster-whisper gradio

# --- アプリ(.app)の生成 ---
echo ""
echo "[5/5] アプリを生成中..."
INSTALL_DIR="$(pwd)"
APP_NAME="文字起こし.app"
APP_DIR="/Applications/$APP_NAME"

# 既存があれば削除
rm -rf "$APP_DIR"

# テンプレートからコピー
cp -R app_template "$APP_DIR"

# インストール先パスを記録
echo "$INSTALL_DIR" > "$APP_DIR/Contents/Resources/install_path.txt"

echo "✓ アプリを /Applications に配置しました"

echo ""
echo "=================================================="
echo " インストール完了! 🎉"
echo "=================================================="
echo ""
echo "Launchpad または /Applications から"
echo "「文字起こし」アプリを起動してください。"
echo ""
echo "※ 初回起動時に「開発元が未確認」と出たら:"
echo "   右クリック → 「開く」で起動できます。"
echo ""
read -p "Enterキーを押してウィンドウを閉じる..."
