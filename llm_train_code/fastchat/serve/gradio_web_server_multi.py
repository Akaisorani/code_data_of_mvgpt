import argparse
import threading
from collections import defaultdict
import datetime
import json
import os
import time
import uuid
import os

from langchain import PromptTemplate

from fastchat import client
import gradio as gr
import requests
import pandas as pd
from fastchat import conversation
from fastchat.client.theme import adjust_theme
from fastchat.conversation import (
    get_default_conv_template,
    compute_skip_echo_len,
    SeparatorStyle, conv_qa_prompt_template,
)
from fastchat.constants import LOGDIR
from fastchat.serve.aurora import AuroraClient
from fastchat.serve.aurora_server import execute_tool_request
from fastchat.serve.chains.knowledge_search import get_prompt_knowledge
from fastchat.serve.util import sendChatRecords, getModelReturn
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

disable_plot = gr.BarPlot.update(
    pd.DataFrame({
        '日期': ['A'],
        '值': [28]
    }),
    x="日期",
    y="值",
    title="Simple Bar Plot with made up data",
    tooltip=['日期', '值'],
    visible=False
)
model_selector = None
scence_selector = None
controller_url = None
enable_moderation = False
models = []
default_aurora_client = AuroraClient()
global_url_base = 'https://pre2-aurora.XXX-inc.com'
default_headers = {
    'Connection': 'keep-alive',
    'Accept': '*/*',
    'Content-Type': 'application/json;charset=UTF-8'
}

priority = {
    "vicuna-13b": "aaa",
    "koala-13b": "aab",
    "oasst-sft-1-pythia-12b": "aac",
    "dolly-v2-12b": "aad",
    "chatglm-6b": "aae",
}


def login(username, password):
    print(username, password)
    if username is None or len(username) == 0 or password is None or len(password) == 0:
        return False
    if not checkLogInFromAurora(username):
        return False
    if password != "admin":
        return False
    return True


def checkLogInFromAurora(userId):
    response = default_aurora_client.doPost(global_url_base + "/auroraAPI/ai-service/log-in/", default_headers, {
        "authentication": {
            "project": "17560",
            "userId": userId
        },
        "param": {

        }
    })
    print(response)
    response_dict = json.loads(response.content.decode("utf8"))
    print(response_dict)
    if response_dict['flag']:
        return True
    else:
        return False


def refresh_models():
    global models
    global controller_url
    global model_selector
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
    dropdown_update = gr.Dropdown.update(choices=models, value=models[0] if len(models) > 0 else "", visible=True)
    state = None
    return (
        state,
        dropdown_update,
        gr.Chatbot.update(visible=True),
        gr.Textbox.update(visible=True),
        gr.Button.update(visible=True),
        gr.Row.update(visible=True),
        gr.Accordion.update(visible=True),
        disable_plot,
        gr.Dropdown.update(visible=True)
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
    return ("",) + (disable_btn,) * 3


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
    if model_name is None:
        print("model_name is None")
        return (state, [], "", '', gr.Dropdown.update(choices=models)) + (disable_btn,) * 5

    if 'chatglm' in model_name or 'm6' in model_name:
        with open('chatglm_help.txt', 'r') as f:
            # 读取文件内容
            help_txt = f.readlines()
            help_txt_lines = ''
            for line in help_txt:
                help_txt_lines = help_txt_lines + line
        help_textbox = gr.Textbox.update(label='你好，我是营销小助手，欢迎体验！你可以尝试问我一下问题：', value=help_txt_lines, max_lines=30,
                                         visible=True)
        return (state, [], "", help_textbox, gr.Dropdown.update(choices=models)) + (disable_btn,) * 5 + (disable_plot,) * 1
    else:
        help_textbox = gr.Textbox.update(label='你好，我是营销小助手，欢迎体验！你可以尝试问我一下问题：', value='', max_lines=30, visible=False)
        return (state, [], "", help_textbox, gr.Dropdown.update(choices=models)) + (disable_btn,) * 5 + (disable_plot,) * 1


def flash_blur():
    return gr.Dropdown.update(choices=models)


def add_text(state, text, model_selector, request: gr.Request):
    logger.info(f"add_text. ip: {request.client.host}. len: {len(text)}")

    if state is None:
        state = get_default_conv_template(model_selector).copy()

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


def http_bot(state, model_selector, temperature, max_new_tokens, scence_selector, request: gr.Request):
    logger.info(f"http_bot. ip: {request.client.host}")
    start_tstamp = time.time()
    model_name = model_selector
    temperature = float(temperature)
    max_new_tokens = int(max_new_tokens)
    plot = disable_plot
    if state.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5 + (disable_plot,) * 1
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
    print(state)
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
            disable_plot
        )
        return

    # Construct prompt
    if "chatglm" in model_name:
        prompt = state.messages[state.offset:]
    elif "analyticai" in model_name:
        prompt = state.get_prompt(state.get_prompt)
    else:
        prompt = state.get_prompt(state.get_prompt)
    skip_echo_len = compute_skip_echo_len(model_name, state, prompt)


    yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5 + (disable_plot,) * 1

    try:
        if(scence_selector == '知识库问答'):
            query = state.messages[-2][1]
            question, answer = get_prompt_knowledge(query, 'XXX_kgb_cmop_p4p_cmop_n_nopass_knowledges_embedding_knlg_data')
            prompt_template = PromptTemplate(
                template=conv_qa_prompt_template,
                input_variables=["context_question", "context_answer", "question"]
            )
            result = prompt_template.format(context_question="\n" + question, context_answer="\n" + answer, question=query)
            state.messages[-2][1] = result
            if "chatglm" in model_name:
                prompt = state.messages[state.offset:]
            elif "analyticai" in model_name:
                prompt = state.get_prompt(model_name)
            else:
                prompt = state.get_prompt(model_name)

            # Make requests
            pload = {
                "model": model_name,
                "prompt": prompt,
                "temperature": temperature,
                "max_new_tokens": max_new_tokens,
                "stop": state.sep if state.sep_style == SeparatorStyle.SINGLE else state.sep2,
            }
            logger.info(f"==== request ====\n{pload}")
            state.messages[-2][1] = query
            state.messages[-1][-1] = "▌"
            skip_echo_len = compute_skip_echo_len(model_name, state, prompt)
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
                        if 'm6' in model_name:
                            if len(output) > 5 and (output.startswith("ToolParam:") or output.startswith("Assistant:")):
                                new_output = output[len("Assistant: "):]
                                state.messages[-1][-1] = new_output + "▌"
                                yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5 + (disable_plot,) * 1
                        else:
                            state.messages[-1][-1] = output + "▌"
                            yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5 + (disable_plot,) * 1
                    else:
                        output = data["text"] + f" (error_code: {data['error_code']})"
                        state.messages[-1][-1] = output
                        yield (state, state.to_gradio_chatbot()) + (
                            disable_btn,
                            disable_btn,
                            disable_btn,
                            enable_btn,
                            enable_btn,
                            disable_plot
                        )
                        return
                    time.sleep(0.02)
        else :
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
            if 'analyticai' in model_name and ('帮助' in prompt or 'help' in prompt):
                output = prompt
            else:
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
                            if 'm6' in model_name:
                                if len(output) > 5 and (output.startswith("ToolParam:") or output.startswith("Assistant:")):
                                        new_output = output[len("Assistant: "):]
                                        state.messages[-1][-1] = new_output + "▌"
                                        yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5 + (disable_plot,) * 1
                            else:
                                state.messages[-1][-1] = output + "▌"
                                yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5 + (disable_plot,) * 1
                        else:
                            output = data["text"] + f" (error_code: {data['error_code']})"
                            state.messages[-1][-1] = output
                            yield (state, state.to_gradio_chatbot()) + (
                                disable_btn,
                                disable_btn,
                                disable_btn,
                                enable_btn,
                                enable_btn,
                                disable_plot
                            )
                            return
                        time.sleep(0.02)
            if 'analyticai' in model_name:
                message, sql_result, plot = getModelReturn(output)
                output = message + "\n" + sql_result
                print('output:' + output)
                state.messages[-1][-1] = message + "\n" + sql_result
                yield (state,
                       state.to_gradio_chatbot()) + (
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          plot
                      )
            elif 'm6' in model_name:
                if output.startswith("Tool:"):
                    new_response = output[len("Tool: "):]
                    try:
                        tool_id = json.loads(new_response)['tool_id']
                        tool_response = execute_tool_request(new_response)
                        tool_response = json.loads(tool_response)
                        assert tool_response["success"] == True
                        tool_response = json.loads(tool_response["value"])
                        if tool_id == 'diagnosis':
                            response = tool_response["data"]["diagnosis"]
                            response = response.replace("&#9;", "").replace("<br>", "\n").strip()
                        elif tool_id == 'kr':
                            tool_response = json.loads(tool_response["data"]["text"])
                            words = [item["keyword"] for item in tool_response["keywords"]]
                            response = "推荐关键词：" + "，".join(words) + "。"
                        else:
                            assert False
                    except IndexError as e:
                        response = "抱歉，未检索到您输入的单元id，可能为id输入有误或数据延迟导致，请您重新确认或稍后再试。"
                    except:
                        response = "抱歉，该功能暂时繁忙，请您稍后再试。"
                    state.messages[-1][-1] = response
                    yield (state,
                       state.to_gradio_chatbot()) + (
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          disable_btn,
                          disable_plot
                      )

    except requests.exceptions.RequestException as e:
        state.messages[-1][-1] = server_error_msg + f" (error_code: 4)"
        yield (state, state.to_gradio_chatbot()) + (
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
            disable_plot
        )
        return

    state.messages[-1][-1] = state.messages[-1][-1][:-1]
    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5 + (plot,) * 1

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
    with gr.Row(elem_id="scenes_row"):
        global scence_selector
        scence_selector = gr.Dropdown(
            choices=['原始问答', '知识库问答'],
            value = '原始问答',
            interactive=True,
            show_label=False,
        ).style(container=False)
    with gr.Row(elem_id="model_selector_row"):
        global model_selector
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
    if len(models) > 0 and ('chatglm' in models[0] or 'm6' in models[0]):
        help = gr.Textbox(label='你好，我是营销小助手，欢迎体验！你可以尝试问我以下问题：', value=help_txt_lines, max_lines=30, visible=True)
    else:
        help = gr.Textbox(label='你好，我是营销小助手，欢迎体验！你可以尝试问我以下问题：', value=help_txt_lines, max_lines=30, visible=False)
    chatbot = grChatbot(elem_id="chatbot", visible=False).style(height=550)
    # 条形图展示
    plot = gr.BarPlot(show_label=False, visible=False).style(container=True)
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
        [textbox, upvote_btn, downvote_btn, flag_btn],
    )
    flag_btn.click(
        flag_last_response,
        [state, model_selector],
        [textbox, upvote_btn, downvote_btn, flag_btn],
    )
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens, scence_selector],
        [state, chatbot] + btn_list + [plot],
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

    model_selector.change(model_selector_clear_history, model_selector,
                          [state, chatbot, textbox, help, model_selector] + btn_list + [plot])
    model_selector.blur(flash_blur, None, model_selector)
    textbox.submit(
        add_text, [state, textbox, model_selector], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens, scence_selector],
        [state, chatbot] + btn_list + [plot],
    )
    send_btn.click(
        add_text, [state, textbox, model_selector], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, model_selector, temperature, max_output_tokens, scence_selector],
        [state, chatbot] + btn_list + [plot],
    )

    return state, model_selector, chatbot, textbox, send_btn, button_row, parameter_row, plot, scence_selector


def build_demo():
    set_theme = adjust_theme()
    with gr.Blocks(
            title="MarketingGLM",
            theme=set_theme,
            # theme=gr.themes.Base(),
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
            plot,
            scence
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
                plot,
                scence
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
        server_name=args.host, server_port=args.port, share=False, max_threads=200, auth=login, auth_message="请输入工号和密码"
        # server_name=args.host, server_port=args.port, share=True, max_threads=200
    )
