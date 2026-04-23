"""
Whisper文字起こしアプリ
ドラッグ&ドロップで音声/動画ファイルをテキスト化
"""

import os
import sys
import signal
import webbrowser
import threading
import time
import traceback
import logging
import tempfile
import shutil
from pathlib import Path

# ログ設定（ファイルとコンソールに出力）
LOG_FILE = Path(__file__).parent / "dicto.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

import platform
import gradio as gr
from faster_whisper import WhisperModel

# ===== 設定 =====
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
IS_APPLE_SILICON = platform.machine() == "arm64"
DEFAULT_MODEL = "turbo" if IS_APPLE_SILICON else "medium"
AUTO_SHUTDOWN_MINUTES = 30  # 最後の操作からこの時間で自動終了

# MLXモデル設定
MLX_MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
}

# ==================

# モデルキャッシュ
current_model = {"name": None, "instance": None}

# 自動終了タイマー
shutdown_timer = {"timer": None}


def reset_shutdown_timer():
    """自動終了タイマーをリセット"""
    if shutdown_timer["timer"] is not None:
        shutdown_timer["timer"].cancel()
    t = threading.Timer(AUTO_SHUTDOWN_MINUTES * 60, auto_shutdown)
    t.daemon = True
    t.start()
    shutdown_timer["timer"] = t


def auto_shutdown():
    """自動終了"""
    logger.info(f"{AUTO_SHUTDOWN_MINUTES}分間操作がなかったため、自動終了します。")
    os.kill(os.getpid(), signal.SIGTERM)


def is_mlx_model(model_size):
    return model_size in MLX_MODELS

def get_model(model_size):
    """モデルを取得(同じモデルなら再ロードしない)"""
    if current_model["name"] == model_size:
        return current_model["instance"]

    logger.info(f"モデルを読み込み中: {model_size} ...")
    if is_mlx_model(model_size):
        # mlx-whisperはモジュール自体がモデルを管理するのでNone
        current_model["instance"] = None
    else:
        model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE)
        current_model["instance"] = model
    current_model["name"] = model_size
    logger.info(f"モデル {model_size} の準備完了")
    return current_model["instance"]


def transcribe(audio_file, language, model_size, save_dir, progress=gr.Progress()):
    """音声ファイルを文字起こしする"""
    logger.info(f"transcribe開始: file={audio_file}, lang={language}, model={model_size}")
    if audio_file is None:
        return "ファイルをアップロードしてください。", "", "", None

    # 操作があったのでタイマーリセット
    reset_shutdown_timer()

    try:
        progress(0, desc="モデルを準備中...")

        # モデル取得(初回 or 変更時にロード)
        model = get_model(model_size)

        progress(0.05, desc="準備完了")

        # 言語設定
        lang = None if language == "自動検出" else language

        progress(0.1, desc="文字起こし中... (時間がかかります)")

        result_text = []
        timestamped_text = []

        if is_mlx_model(model_size):
            import mlx_whisper
            decode_opts = {} if lang is None else {"language": lang}
            mlx_result = mlx_whisper.transcribe(
                audio_file,
                path_or_hf_repo=MLX_MODELS[model_size],
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                no_speech_threshold=0.6,
                hallucination_silence_threshold=2.0,
                **decode_opts,
            )
            detected_lang = mlx_result.get("language", lang or "?")
            segments_list = mlx_result.get("segments", [])
            total_duration = segments_list[-1]["end"] if segments_list else 0
            logger.info(f"文字起こし開始(MLX): 長さ={format_time(total_duration)}, 言語={detected_lang}")

            for i, seg in enumerate(segments_list):
                text = seg["text"].strip()
                if not text:
                    continue
                result_text.append(text)
                start = format_time(seg["start"])
                end = format_time(seg["end"])
                timestamped_text.append(f"[{start} - {end}] {text}")

            progress(0.9, desc="文字起こし完了")
        else:
            segments, info = model.transcribe(
                audio_file,
                language=lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                no_speech_threshold=0.6,
            )
            total_duration = info.duration
            detected_lang = info.language
            logger.info(f"文字起こし開始: 長さ={format_time(total_duration)}, 言語={detected_lang}")

            seg_count = 0
            for segment in segments:
                seg_count += 1
                result_text.append(segment.text.strip())
                start = format_time(segment.start)
                end = format_time(segment.end)
                timestamped_text.append(f"[{start} - {end}] {segment.text.strip()}")

                if seg_count % 50 == 1:
                    logger.info(f"処理中: セグメント{seg_count}, {end} / {format_time(total_duration)}")

                progress_val = min(0.1 + (segment.end / total_duration) * 0.85, 0.95)
                progress(progress_val, desc=f"文字起こし中... ({format_time(segment.end)} / {format_time(total_duration)})")

        progress(0.95, desc="ファイル保存中...")

        plain_text = "\n".join(result_text)
        timestamped = "\n".join(timestamped_text)

        # 結果テキストを作成
        file_content = f"=== 文字起こし結果 ===\n"
        file_content += f"元ファイル: {Path(audio_file).name}\n"
        file_content += f"検出言語: {detected_lang}\n"
        file_content += f"使用モデル: {model_size}\n"
        file_content += f"長さ: {format_time(total_duration)}\n\n"
        file_content += "=== 本文 ===\n"
        file_content += plain_text
        file_content += "\n\n=== タイムスタンプ付き ===\n"
        file_content += timestamped

        # ユーザー指定の保存先に保存
        save_path = Path(save_dir.strip()) if save_dir and save_dir.strip() else Path.home() / "Desktop"
        if not save_path.exists():
            save_path = Path.home() / "Desktop"

        base_name = Path(audio_file).stem
        output_file = save_path / f"{base_name}_文字起こし.txt"

        counter = 1
        while output_file.exists():
            output_file = save_path / f"{base_name}_文字起こし_{counter}.txt"
            counter += 1

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(file_content)

        # Gradioダウンロード用に一時ファイルを作成
        tmp_file = Path(tempfile.gettempdir()) / output_file.name
        shutil.copy2(output_file, tmp_file)

        progress(1.0, desc="完了!")

        info_text = f"✓ 完了しました!\n\n検出言語: {detected_lang}\n使用モデル: {model_size}\n長さ: {format_time(total_duration)}\n保存先: {output_file}"

        return plain_text, timestamped, info_text, str(tmp_file)

    except Exception as e:
        logger.error(f"文字起こしエラー: {e}", exc_info=True)
        return f"エラーが発生しました: {str(e)}", "", "", None


def format_time(seconds):
    """秒を HH:MM:SS 形式に"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ===== Gradio UI =====
with gr.Blocks(title="文字起こしアプリ") as app:
    gr.Markdown("""
    # 🎙️ 文字起こしアプリ

    音声ファイルや動画ファイルをドラッグ&ドロップすると、文字起こしをします。

    **対応形式**: mp3, wav, m4a, mp4, mov, その他ffmpeg対応の音声・動画形式
    """)

    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                label="ここに音声・動画ファイルをドラッグ&ドロップ",
                type="filepath",
                sources=["upload"],
            )
            language = gr.Dropdown(
                choices=["自動検出", "ja", "en", "zh", "ko"],
                value="ja",
                label="言語(日本語なら ja のままでOK)",
            )
            with gr.Accordion("⚙️ 設定", open=False):
                model_choices = ["turbo", "tiny", "base", "small", "medium", "large-v3"] if IS_APPLE_SILICON else ["tiny", "base", "small", "medium", "large-v3"]
                model_choice = gr.Radio(
                    choices=model_choices,
                    value=DEFAULT_MODEL,
                    label="モデルサイズ",
                    info="turbo→Apple Silicon高速/高精度, medium→バランス, large-v3→最高精度/遅い" if IS_APPLE_SILICON else "tiny→速い/低精度, medium→バランス, large-v3→高精度/遅い",
                )
                save_dir_input = gr.Textbox(
                    label="保存先フォルダ",
                    value=str(Path.home() / "Desktop"),
                    info="結果ファイルの保存先。空欄ならデスクトップに保存",
                )
            submit_btn = gr.Button("文字起こしを開始", variant="primary", size="lg")

        with gr.Column(scale=2):
            status = gr.Textbox(label="状態", lines=4)

            with gr.Tabs():
                with gr.Tab("本文"):
                    text_output = gr.Textbox(
                        label="文字起こし結果",
                        lines=20,
                    )
                with gr.Tab("タイムスタンプ付き"):
                    timestamped_output = gr.Textbox(
                        label="タイムスタンプ付き結果",
                        lines=20,
                    )

            download_file = gr.File(label="結果ファイル")

    submit_btn.click(
        fn=transcribe,
        inputs=[audio_input, language, model_choice, save_dir_input],
        outputs=[text_output, timestamped_output, status, download_file],
    )

    gr.Markdown(f"""
    ---
    **使い方のコツ**
    - 長い音声は時間がかかります(1時間の音声で10〜30分程度)
    - 処理中はこのウィンドウを閉じないでください
    - {AUTO_SHUTDOWN_MINUTES}分間操作がないと自動で終了します(メモリ節約のため)
    """)


def open_browser():
    """少し待ってからブラウザを開く"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:7860")


def kill_existing():
    """既存のdictoプロセスがポートを使っていたら停止"""
    import subprocess
    result = subprocess.run(["lsof", "-ti:7860"], capture_output=True, text=True)
    for pid in result.stdout.strip().split("\n"):
        if pid and int(pid) != os.getpid():
            os.kill(int(pid), signal.SIGTERM)
            time.sleep(1)


if __name__ == "__main__":
    # 既存プロセスを停止
    kill_existing()

    # 自動終了タイマー開始
    reset_shutdown_timer()

    # ブラウザ自動起動
    threading.Thread(target=open_browser, daemon=True).start()

    # アプリ起動
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        inbrowser=False,
        theme=gr.themes.Soft(),
    )
