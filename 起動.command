#!/bin/bash
# Whisper文字起こしアプリ 起動スクリプト

cd "$(dirname "$0")"

# 仮想環境が存在するか確認
if [ ! -d "venv" ]; then
    echo "エラー: まず「install.command」を実行してください。"
    read -p "Enterキーで閉じる..."
    exit 1
fi

echo "=================================================="
echo " Whisper文字起こしアプリを起動中..."
echo "=================================================="
echo ""
echo "ブラウザが自動で開きます。"
echo "このウィンドウは閉じないでください(閉じるとアプリが停止します)"
echo ""
echo "アプリを終了するときは Ctrl+C を押してください。"
echo ""

PYTHON="$(cd "$(dirname "$0")" && pwd)/venv/bin/python"
caffeinate -is "$PYTHON" "$(cd "$(dirname "$0")" && pwd)/app.py"
