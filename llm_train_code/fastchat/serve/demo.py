import argparse
import shutil
import os
import subprocess
import threading
import time
import logging
import gradio as gr

from fastchat.client.theme import adjust_theme
from fastchat.utils import (
    build_logger,
    server_error_msg,
    violates_moderation,
    moderation_msg,
)

log = build_logger("modelTrainAndUpload", "modelTrainAndUpload.log")

import requests
from fastchat.utils import (
    build_logger
)
from fastchat.serve.gradio_patch import Chatbot as grChatbot
from fastchat.serve.gradio_css import code_highlight_css
from zipfile import ZipFile

logger = build_logger("gradio_web_model_train", "gradio_web_model_train.log")

headers = {"User-Agent": "fastchat Client"}

no_change_btn = gr.Button.update()
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=False)

controller_url = None
enable_moderation = False
models = []


def set_global_vars(controller_url_, enable_moderation_, models_):
    global controller_url, enable_moderation, models
    controller_url = controller_url_
    enable_moderation = enable_moderation_
    models = models_


def get_model_list(controller_url):
    ret = requests.post(controller_url + "/refresh_all_workers")
    assert ret.status_code == 200
    ret = requests.post(controller_url + "/list_models")
    models = ret.json()["models"]
    # models.sort(key=lambda x: priority.get(x, x))
    logger.info(f"Models: {models}")
    return models


def refresh_models():
    global models
    global controller_url
    # refresh options here
    flash_models = get_model_list(controller_url)
    models = flash_models
    print(models)


def flash_blur():
    refresh_models
    return gr.Dropdown.update(choices=models)


get_window_url_params = """
function() {
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    console.log(url_params);
    return url_params;
    }
"""


def load_demo_single(url_params):
    dropdown_update = gr.Dropdown.update(visible=True)
    if "model" in url_params:
        model = url_params["model"]
        if model in models:
            dropdown_update = gr.Dropdown.update(value=model, visible=True)

    state = None
    return (
        state,
        dropdown_update,
        gr.Chatbot.update(visible=True),
        gr.Textbox.update(visible=True),
        gr.Button.update(visible=True),
        gr.Row.update(visible=True),
        gr.Accordion.update(visible=True),
    )


notice_markdown = """
# 🏔️ MarketingGLM
## 由于数据安全原因，体验请使用[XXX平台](http://aurora.XXX-inc.com/)

"""

learn_more_markdown = """
最终解释权归XXX所有
"""

block_css = (
        code_highlight_css
        + """
pre {
    white-space: pre-wrap;       /* Since CSS 2.1 */
    white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
    white-space: -pre-wrap;      /* Opera 4-6 */
    white-space: -o-pre-wrap;    /* Opera 7 */
    word-wrap: break-word;       /* Internet Explorer 5.5+ */
}
"""
)
running_models = []
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=False)




def train_ui():
    state = gr.State()

    # Draw layout
    show = gr.Markdown(notice_markdown)

    notice = gr.Markdown(learn_more_markdown)

    return state


def build_demo():
    set_theme = adjust_theme()
    with gr.Blocks(
            title="MarketingGLM",
            theme=set_theme,
            css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)
        train_ui()
    return demo


# share=False must be set to meet the data security policy of XXX
if __name__ == "__main__":
    gr.close_all()
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--concurrency-count", type=int, default=10)

    args = parser.parse_args()
    logger.info(f"args: {args}")

    gr.close_all()
    demo = build_demo()
    demo.queue(
        concurrency_count=args.concurrency_count, status_update_rate=10, api_open=False
    ).launch(
        server_name=args.host, server_port=args.port, share=False, max_threads=200
    )
