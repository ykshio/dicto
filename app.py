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
from pathlib import Path

import gradio as gr
from faster_whisper import WhisperModel

# ===== 設定 =====
DEVICE = "cpu"  # MacではCPU推奨(CoreML対応は別途必要)
COMPUTE_TYPE = "int8"  # int8は軽量で実用的
DEFAULT_MODEL = "medium"
AUTO_SHUTDOWN_MINUTES = 30  # 最後の操作からこの時間で自動終了

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
    print(f"\n{AUTO_SHUTDOWN_MINUTES}分間操作がなかったため、自動終了します。")
    os.kill(os.getpid(), signal.SIGTERM)


def get_model(model_size):
    """モデルを取得(同じモデルなら再ロードしない)"""
    if current_model["name"] == model_size:
        return current_model["instance"]

    print(f"モデルを読み込み中: {model_size} ...")
    model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE)
    current_model["name"] = model_size
    current_model["instance"] = model
    print(f"✓ モデル {model_size} の準備完了!")
    return model


# 起動時にデフォルトモデルをロード
get_model(DEFAULT_MODEL)


def transcribe(audio_file, language, model_size, save_dir, progress=gr.Progress()):
    """音声ファイルを文字起こしする"""
    if audio_file is None:
        return "ファイルをアップロードしてください。", "", "", None

    # 操作があったのでタイマーリセット
    reset_shutdown_timer()

    progress(0, desc="準備中...")

    # モデル取得(変更があればここでリロード)
    model = get_model(model_size)

    # 言語設定
    lang = None if language == "自動検出" else language

    progress(0.1, desc="文字起こし中... (時間がかかります)")

    try:
        segments, info = model.transcribe(
            audio_file,
            language=lang,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
            condition_on_previous_text=False,  # ループ対策
            compression_ratio_threshold=2.4,   # 繰り返し検出
            no_speech_threshold=0.6,           # 無音の幻聴抑制
        )

        # 結果を集める
        result_text = []
        timestamped_text = []

        total_duration = info.duration

        for segment in segments:
            result_text.append(segment.text.strip())
            start = format_time(segment.start)
            end = format_time(segment.end)
            timestamped_text.append(f"[{start} - {end}] {segment.text.strip()}")

            progress_val = min(0.1 + (segment.end / total_duration) * 0.85, 0.95)
            progress(progress_val, desc=f"文字起こし中... ({format_time(segment.end)} / {format_time(total_duration)})")

        progress(0.95, desc="ファイル保存中...")

        plain_text = "\n".join(result_text)
        timestamped = "\n".join(timestamped_text)

        # 保存先の決定
        save_path = Path(save_dir.strip()) if save_dir and save_dir.strip() else Path.home() / "Desktop"
        if not save_path.exists():
            save_path = Path.home() / "Desktop"

        base_name = Path(audio_file).stem
        output_file = save_path / f"{base_name}_文字起こし.txt"

        # 重複回避
        counter = 1
        while output_file.exists():
            output_file = save_path / f"{base_name}_文字起こし_{counter}.txt"
            counter += 1

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"=== 文字起こし結果 ===\n")
            f.write(f"元ファイル: {Path(audio_file).name}\n")
            f.write(f"検出言語: {info.language}\n")
            f.write(f"使用モデル: {model_size}\n")
            f.write(f"長さ: {format_time(info.duration)}\n\n")
            f.write("=== 本文 ===\n")
            f.write(plain_text)
            f.write("\n\n=== タイムスタンプ付き ===\n")
            f.write(timestamped)

        progress(1.0, desc="完了!")

        info_text = f"✓ 完了しました!\n\n検出言語: {info.language}\n使用モデル: {model_size}\n長さ: {format_time(info.duration)}\n保存先: {output_file}"

        return plain_text, timestamped, info_text, str(output_file)

    except Exception as e:
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
                model_choice = gr.Radio(
                    choices=["tiny", "base", "small", "medium", "large-v3"],
                    value=DEFAULT_MODEL,
                    label="モデルサイズ",
                    info="tiny→速い/低精度, medium→バランス, large-v3→高精度/遅い",
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


if __name__ == "__main__":
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
