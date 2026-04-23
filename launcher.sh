#!/bin/bash
# dicto バックグラウンドランチャー
# AppleScriptアプリから呼ばれる

INSTALL_DIR="$HOME/dicto"

# Homebrew PATHを設定（AppleScriptからはPATHが最小限のため）
if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -f /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# 既に起動中ならブラウザだけ開く
if lsof -ti:7860 >/dev/null 2>&1; then
    open "http://127.0.0.1:7860"
    exit 0
fi

# 起動通知
osascript -e 'display notification "起動しています..." with title "dicto"'

# pythonをバックグラウンドで起動
cd "$INSTALL_DIR"
caffeinate -is ./venv/bin/python app.py &

# サーバー起動を待つ
for i in $(seq 1 120); do
    if curl -s -o /dev/null http://127.0.0.1:7860 2>/dev/null; then
        osascript -e 'display notification "準備完了" with title "dicto"'
        open "http://127.0.0.1:7860"
        exit 0
    fi
    sleep 1
done

osascript -e 'display dialog "起動に失敗しました。もう一度お試しください。" buttons {"OK"} default button "OK" with icon stop with title "dicto"'
exit 1
