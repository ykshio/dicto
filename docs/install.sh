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
    echo ""
    echo "※ Macのログインパスワードを求められます。入力しても画面には表示されませんが、正常です。"
    echo ""
    # パイプ経由だとstdinが使えずsudoが失敗するため、一度ファイルに保存して実行
    BREW_INSTALLER=$(mktemp)
    curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$BREW_INSTALLER"
    /bin/bash "$BREW_INSTALLER" </dev/tty
    rm -f "$BREW_INSTALLER"

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

# 実行権限を付与
chmod +x launcher.sh app_template/Contents/MacOS/launch

# --- Python仮想環境 ---
echo "[4/5] Python環境をセットアップ中..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install faster-whisper gradio -q
# Apple Siliconの場合はMLXもインストール
if [ "$(uname -m)" = "arm64" ]; then
    echo "    Apple Silicon検出: MLX高速モデルをインストール中..."
    ./venv/bin/pip install mlx-whisper -q
fi

# --- .appの生成 ---
echo "[5/5] アプリを生成中..."
APP_DIR="/Applications/dicto.app"
rm -rf "$APP_DIR" 2>/dev/null || true

if osacompile -o "$APP_DIR" -e '
on run
    set home to POSIX path of (path to home folder)
    set launcherPath to home & "dicto/launcher.sh"
    try
        do shell script "test -f " & quoted form of launcherPath
    on error
        display dialog "dictoがインストールされていません。" & return & "インストールコマンドを実行してください。" buttons {"OK"} default button "OK" with icon stop with title "dicto"
        return
    end try
    do shell script quoted form of launcherPath & " &>/dev/null &"
end run
' 2>/dev/null; then
    # アイコンを設定
    cp app_template/Contents/Resources/icon.icns "$APP_DIR/Contents/Resources/applet.icns" 2>/dev/null || true
    echo "✓ /Applications/dicto.app を作成しました"
else
    echo ""
    echo "⚠️  アプリの生成に失敗しました。以下のコマンドで直接起動できます:"
    echo "    cd ~/dicto && ./venv/bin/python app.py"
fi

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
