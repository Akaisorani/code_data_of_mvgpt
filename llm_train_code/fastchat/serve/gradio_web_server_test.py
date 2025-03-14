import argparse
import threading
from collections import defaultdict
import datetime
import json
import os
import time
import uuid

import gradio as gr
import requests

from fastchat import conversation
from fastchat.conversation import (
    get_default_conv_template,
    compute_skip_echo_len,
    SeparatorStyle,
)
from fastchat.constants import LOGDIR
from fastchat.serve.chains.knowledge_search import get_prompt_knowledge_top_k
from fastchat.serve.util import sendChatRecords
from fastchat.utils import (
    build_logger,
    server_error_msg,
    violates_moderation,
    moderation_msg,
)
from fastchat.serve.gradio_patch import Chatbot as grChatbot
from fastchat.serve.gradio_css import code_highlight_css

logger = build_logger("gradio_web_server", "gradio_web_server.log")

headers = {"User-Agent": "fastchat Client"}

no_change_btn = gr.Button.update()
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=False)

controller_url = None
enable_moderation = False
models = []

priority = {
    "vicuna-13b": "aaa",
    "koala-13b": "aab",
    "oasst-sft-1-pythia-12b": "aac",
    "dolly-v2-12b": "aad",
    "chatglm-6b": "aae",
}


def refresh_models():
    global models
    global controller_url
    # refresh options here
    flash_models = get_model_list(controller_url)
    models = flash_models
    threading.Timer(5.0, refresh_models).start()
    print(models)


def my_custom_sort(lst):
    n = len(lst)
    for i in range(n):
        for j in range(i + 1, n):
            if 'chatglm' in lst[j]:
                lst[i], lst[j] = lst[j], lst[i]
    return lst


def set_global_vars(controller_url_, enable_moderation_, models_):
    global controller_url, enable_moderation, models
    controller_url = controller_url_
    enable_moderation = enable_moderation_
    models = models_


def get_conv_log_filename():
    t = datetime.datetime.now()
    name = os.path.join(LOGDIR, f"{t.year}-{t.month:02d}-{t.day:02d}-conv.json")
    return name


def get_model_list(controller_url):
    ret = requests.post(controller_url + "/refresh_all_workers")
    assert ret.status_code == 200
    ret = requests.post(controller_url + "/list_models")
    models = ret.json()["models"]
    # models.sort(key=lambda x: priority.get(x, x))
    models = my_custom_sort(models)
    logger.info(f"Models: {models}")
    return models


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


def load_demo(url_params, request: gr.Request):
    logger.info(f"load_demo. ip: {request.client.host}. params: {url_params}")
    return load_demo_single(url_params)


def vote_last_response(state, vote_type, model_selector, request: gr.Request):
    with open(get_conv_log_filename(), "a") as fout:
        data = {
            "tstamp": round(time.time(), 4),
            "type": vote_type,
            "model": model_selector,
            "state": state.dict(),
            "ip": request.client.host,
        }
        fout.write(json.dumps(data) + "\n")
    sendChatRecords(input=state.messages[-2][1], output=state.messages[-1][1], modelName=model_selector, userId=None,
                    tag=vote_type)


def upvote_last_response(state, model_selector, request: gr.Request):
    logger.info(f"upvote. ip: {request.client.host}")
    vote_last_response(state, "upvote", model_selector, request)
    return ("",) + (disable_btn,) * 3


def downvote_last_response(state, model_selector, request: gr.Request):
    logger.info(f"downvote. ip: {request.client.host}")
    vote_last_response(state, "downvote", model_selector, request)
    if 'chatglm' in model_selector:
        query = state.messages[-2][1]
        new_id_list, my_dict = get_prompt_knowledge_top_k(query, 'XXX_kgb_cmop_p4p_cmop_n_nopass_knowledges_embedding_knlg_data', 5)
        response = "\n亲，对不起我的回答有问题，以下是从知识库中的相似的5个回答，请参考：\n"
        index = 1
        for id in new_id_list:
            data = my_dict[id]
            question = str(data[1])
            answer = str(data[2])
            response = response + str(index) + ".问题：" + question + "\n" + str(index) + ".回答：" + answer + "\n"
            index += 1
    state.messages[-1][-1] = state.messages[-1][-1] + "\n" + response
    return ("",) + (disable_btn,) * 3 + (state.to_gradio_chatbot(),) * 1



def flag_last_response(state, model_selector, request: gr.Request):
    logger.info(f"flag. ip: {request.client.host}")
    vote_last_response(state, "flag", model_selector, request)
    return ("",) + (disable_btn,) * 3


def regenerate(state, request: gr.Request):
    logger.info(f"regenerate. ip: {request.client.host}")
    state.messages[-1][-1] = None
    state.skip_next = False
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


def clear_history(request: gr.Request):
    logger.info(f"clear_history. ip: {request.client.host}")
    state = None

    return (state, [], "") + (disable_btn,) * 5

def model_selector_clear_history(model_name, request: gr.Request):
    logger.info(f"clear_history. ip: {request.client.host}")
    state = None
    if 'chatglm' in model_name:
        with open('chatglm_help.txt', 'r') as f:
            # 读取文件内容
            help_txt = f.readlines()
            help_txt_lines = ''
            for line in help_txt:
                help_txt_lines = help_txt_lines + line
        help_textbox = gr.Textbox.update(label='你好，我是营销小助手，欢迎体验！你可以尝试问我以下问题：', value=help_txt_lines, max_lines=30, visible=True)
        return (state, [], "", help_textbox) + (disable_btn,) * 5
    else:
        help_textbox = gr.Textbox.update(visible=False)
        return (state, [], "", help_textbox) + (disable_btn,) * 5


def flash_blur():
    return gr.Dropdown.update(choices=models)


def add_text(state, text, request: gr.Request):
    logger.info(f"add_text. ip: {request.client.host}. len: {len(text)}")

    if state is None:
        state = get_default_conv_template("vicuna").copy()

    if len(text) <= 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "") + (no_change_btn,) * 5
    if enable_moderation:
        flagged = violates_moderation(text)
        if flagged:
            logger.info(f"violate moderation. ip: {request.client.host}. text: {text}")
            state.skip_next = True
            return (state, state.to_gradio_chatbot(), moderation_msg) + (
                no_change_btn,
            ) * 5

    text = text[:1536]  # Hard cut-off
    state.append_message(state.roles[0], text)
    state.append_message(state.roles[1], None)
    state.skip_next = False
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


def post_process_code(code):
    sep = "\n```"
    if sep in code:
        blocks = code.split(sep)
        if len(blocks) % 2 == 1:
            for i in range(1, len(blocks), 2):
                blocks[i] = blocks[i].replace("\\_", "_")
        code = sep.join(blocks)
    return code


def http_bot(state, model_selector, temperature, max_new_tokens, request: gr.Request):
    logger.info(f"http_bot. ip: {request.client.host}")
    start_tstamp = time.time()
    model_name = model_selector
    temperature = float(temperature)
    max_new_tokens = int(max_new_tokens)

    if state.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
        return

    if len(state.messages) == state.offset + 2:
        # First round of conversation
        new_state = get_default_conv_template(model_name).copy()
        new_state.conv_id = uuid.uuid4().hex
        new_state.append_message(new_state.roles[0], state.messages[-2][1])
        new_state.append_message(new_state.roles[1], None)
        state = new_state

    # Query worker address
    ret = requests.post(
        controller_url + "/get_worker_address", json={"model": model_name}
    )
    worker_addr = ret.json()["address"]
    logger.info(f"model_name: {model_name}, worker_addr: {worker_addr}")

    # No available worker
    if worker_addr == "":
        state.messages[-1][-1] = server_error_msg
        yield (
            state,
            state.to_gradio_chatbot(),
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        )
        return

    # Construct prompt
    if "chatglm" in model_name or 'M6' in model_name or 'm6' in model_name:
        prompt = state.messages[state.offset:]
    else:
        prompt = state.get_prompt(state.get_prompt)
    skip_echo_len = compute_skip_echo_len(model_name, state, prompt)

    # Make requests
    pload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens,
        "stop": state.sep if state.sep_style == SeparatorStyle.SINGLE else state.sep2,
    }
    logger.info(f"==== request ====\n{pload}")

    state.messages[-1][-1] = "▌"
    yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5

    try:
        # Stream output
        response = requests.post(
            worker_addr + "/worker_generate_stream",
            headers=headers,
            json=pload,
            stream=True,
            timeout=2000,
        )
        logger.info(response)
        for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode())
                if data["error_code"] == 0:
                    output = data["text"][skip_echo_len:].strip()
                    output = post_process_code(output)
                    state.messages[-1][-1] = output + "▌"
                    yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5
                else:
                    output = data["text"] + f" (error_code: {data['error_code']})"
                    state.messages[-1][-1] = output
                    yield (state, state.to_gradio_chatbot()) + (
                        disable_btn,
                        disable_btn,
                        disable_btn,
                        enable_btn,
                        enable_btn,
                    )
                    return
                time.sleep(0.02)
    except requests.exceptions.RequestException as e:
        state.messages[-1][-1] = server_error_msg + f" (error_code: 4)"
        yield (state, state.to_gradio_chatbot()) + (
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        )
        return

    state.messages[-1][-1] = state.messages[-1][-1][:-1]
    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

    finish_tstamp = time.time()
    logger.info(f"{output}")

    with open(get_conv_log_filename(), "a") as fout:
        data = {
            "tstamp": round(finish_tstamp, 4),
            "type": "chat",
            "model": model_name,
            "gen_params": {
                "temperature": temperature,
                "max_new_tokens": max_new_tokens,
            },
            "start": round(start_tstamp, 4),
            "finish": round(start_tstamp, 4),
            "state": state.dict(),
            "ip": request.client.host,
        }
        fout.write(json.dumps(data) + "\n")


notice_markdown = """
# 🏔️ MarketingGLM
## 欢迎到使用XXX平台体验最新营销智能助手 [XXX平台](http://aurora.XXX-inc.com)  [使用手册](https://XXX.XXX.com/mocqv8/kg7h1z/dhsw9g4r6zif652f?singleDoc#)
"""

learn_more_markdown = """
XXX
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


def build_single_model_ui():
    state = gr.State()

    # Draw layout
    notice = gr.Markdown(notice_markdown)

    with gr.Row(elem_id="model_selector_row"):
        model_selector = gr.Dropdown(
            choices=models,
            value=models[0] if len(models) > 0 else "",
            interactive=True,
            show_label=False,
        ).style(container=False)
    with open('chatglm_help.txt', 'r') as f:
        # 读取文件内容
        help_txt = f.readlines()
        help_txt_lines = ''
        for line in help_txt:
            help_txt_lines = help_txt_lines + line
    if(len(models) > 0 and 'chatglm' in models[0]):
        help = gr.Textbox(label='你好，我是营销小助手，欢迎体验！你可以尝试问我以下问题：', value=help_txt_lines, max_lines=30, visible=True)
    else:
        help = gr.Textbox(label='你好，我是营销小助手，欢迎体验！你可以尝试问我以下问题：', value=help_txt_lines, max_lines=30, visible=False)

    chatbot = grChatbot(elem_id="chatbot", visible=False).style(height=550)
    with gr.Row():
        with gr.Column(scale=20):
            textbox = gr.Textbox(
                show_label=False,
                placeholder="Enter text and press ENTER",
                visible=False,
            ).style(container=False)
        with gr.Column(scale=1, min_width=50):
            send_btn = gr.Button(value="Send", visible=False)

    with gr.Row(visible=False) as button_row:
        upvote_btn = gr.Button(value="👍  Upvote", interactive=False)
        downvote_btn = gr.Button(value="👎  Downvote", interactive=False)
        flag_btn = gr.Button(value="⚠️  Flag", interactive=False)
        # stop_btn = gr.Button(value="⏹️  Stop Generation", interactive=False)
        regenerate_btn = gr.Button(value="🔄  Regenerate", interactive=False)
        clear_btn = gr.Button(value="🗑️  Clear history", interactive=False)

    with gr.Accordion("Parameters", open=False, visible=False) as parameter_row:
        temperature = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.7,
            step=0.1,
            interactive=True,
            label="Temperature",
        )
        max_output_tokens = gr.Slider(
            minimum=0,
            maximum=1024,
            value=512,
            step=64,
            interactive=True,
            label="Max output tokens",
        )

    gr.Markdown(learn_more_markdown)

    # Register listeners
    btn_list = [upvote_btn, downvote_btn, flag_btn, regenerate_btn, clear_btn]
    upvote_btn.click(
        upvote_last_response,
        [state, model_selector],
        [textbox, upvote_btn, downvote_btn, flag_btn],
    )
    downvote_btn.click(
        downvote_last_response,
        [state, model_selector],
        [textbox, upvote_btn, downvote_btn, flag_btn, chatbot],
    )
    flag_btn.click(
        flag_last_response,
        [state, model_selector],
        [textbox, upvote_btn, downvote_btn, flag_btn],
    )
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

    model_selector.change(model_selector_clear_history, model_selector, [state, chatbot, textbox, help] + btn_list)
    model_selector.blur(flash_blur, None, model_selector)
    textbox.submit(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    send_btn.click(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )

    return state, model_selector, chatbot, textbox, send_btn, button_row, parameter_row


def build_demo():
    with gr.Blocks(
            title="MarketingGLM",
            theme=gr.themes.Base(),
            css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)

        (
            state,
            model_selector,
            chatbot,
            textbox,
            send_btn,
            button_row,
            parameter_row,
        ) = build_single_model_ui()

        demo.load(
                load_demo,
                [url_params],
                [
                    state,
                    model_selector,
                    chatbot,
                    textbox,
                    send_btn,
                    button_row,
                    parameter_row,
                ],
                _js=get_window_url_params,
            )

    return demo


# share=False must be set to meet the data security policy of XXX
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--controller-url", type=str, default="http://localhost:21001")
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument(
        "--model-list-mode", type=str, default="once", choices=["once", "reload"]
    )
    parser.add_argument("--share", action="store_true")
    parser.add_argument(
        "--moderate", action="store_true", help="Enable content moderation"
    )
    args = parser.parse_args()
    logger.info(f"args: {args}")

    models = get_model_list(args.controller_url)
    set_global_vars(args.controller_url, args.moderate, models)
    refresh_models()

    logger.info(args)
    gr.close_all()
    demo = build_demo()
    demo.queue(
        concurrency_count=args.concurrency_count, status_update_rate=10, api_open=False
    ).launch(
        server_name=args.host, server_port=args.port, share=False, max_threads=200, auth=('user', 'pass'),
        auth_message='please specify username and password'
        # server_name=args.host, server_port=args.port, share=True, max_threads=200
    )
