import argparse
import json
import shutil
import os
import subprocess
import threading
import time
import logging
import gradio as gr

from fastchat.client.theme import adjust_theme
from fastchat.model.util import OSS
from fastchat.serve.aurora import AuroraClient
from fastchat.serve.controller import get_available_port
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
default_aurora_client = AuroraClient()
global_url_base = 'https://pre2-aurora.alibaba-inc.com'
default_headers = {
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'Content-Type': 'application/json;charset=UTF-8'
        }
oss_models = []
python_path = 'python3'
nebulactl_path = 'nebulactl'

def login(username, password):
    print(username, password)
    if username is None or len(username) == 0 or password is None or len(password) == 0:
        return False
    if not checkLogInFromAurora(username):
        return False
    if password != "password":
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

def set_global_vars(controller_url_, enable_moderation_, models_, oss_models_, python_path_, nebulactl_path_):
    global controller_url, enable_moderation, models, oss_models, python_path, nebulactl_path
    controller_url = controller_url_
    enable_moderation = enable_moderation_
    models = models_
    oss_models = oss_models_
    python_path = python_path_
    nebulactl_path = nebulactl_path_


def get_oss_models():
    global oss_models
    work_dir = "ai_service/models/"
    oss_models = OSS.ls(work_dir)
    logger.info(f"oss_models: {oss_models}")
    return oss_models

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
    refresh_models()
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
# MarketingGLM 训练部署平台
"""

learn_more_markdown = """
Alimama
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


def train_process(data_file, model_name, base_model, queue):
    data_file.seek(0)
    with open(r'train_mdl/' + model_name + '.json', 'w') as out_file:
        shutil.copyfile(data_file.name, out_file.name)
    submit_train_cmd = "nohup sh train_mdl/submit_task.sh {} {} {} {} {} >> log/{}_train.log 2>&1 &".format(
        model_name,
        model_name + '.json',
        base_model,
        queue,
        nebulactl_path,
        model_name,
    )

    log.info("submit_train_cmd= " + submit_train_cmd)
    os.system(submit_train_cmd)
    return disable_btn


def upload_process(model_name):
    port = get_available_port()
    upload_process_cmd = "nohup {} -m fastchat.model.model_upload --oss_path {} --port {} --python_path {} >> log/{}_upload.log  2>&1 &".format(
        python_path,
        'oss://faeet2/ai_service/models/{}/'.format(model_name),
        port,
        python_path,
        model_name
    )
    os.environ["MKL_SERVICE_FORCE_INTEL"] = "1"
    log.info("upload_process_cmd= " + upload_process_cmd)
    os.system(upload_process_cmd)
    return disable_btn, gr.Textbox.update(value=model_name)

def flush_train_log(model_name):
    with open('log/{}_train.log'.format(model_name), 'r') as f:
        # 读取文件内容
        log_data = f.readlines()
    train_log = ''
    for line in log_data:
        train_log = train_log + line

    return gr.Textbox.update(value=train_log, label="训练日志")


def flush_upload_log(model_name):
    with open('log/{}_upload.log'.format(model_name), 'r') as f:
        # 读取文件内容
        log_data = f.readlines()
    upload_log = ''
    for line in log_data:
        upload_log = upload_log + line

    return gr.Textbox.update(value=upload_log, label="部署日志")


def execute_cmd_with_error_timeout(cmd, timeout=60):
    proc = None
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (outs, errs) = proc.communicate(timeout=timeout)
    except Exception as e:
        return -9, '', 'timed out after ' + str(timeout) + ' seconds'
    return proc.returncode, outs.decode("utf8"), errs.decode("utf8")


def get_pid_arr(pName):
    cmd = "ps -ef|grep '" + \
          str(pName) + "' |grep -v grep | grep -v PPID | awk '{ print $2 }'"
    (retCode, outs, error) = execute_cmd_with_error_timeout(cmd)
    return str(outs).strip().split('\n')


def get_pid_info(pid):
    cmd = "ps " + str(pid)
    (code, outs, errs) = execute_cmd_with_error_timeout(cmd)
    if code != 0:
        # log.error('get pid info error, pid is not exist, ' + str(pid))
        return ''
    else:
        return str(outs)


def get_real_pid_arr(processName):
    processCount = 0
    real_pid_arr = []
    pidArr = get_pid_arr(processName)
    for pid in pidArr:
        pidInfo = get_pid_info(pid)
        flag = False
        if processName in pidInfo and 'nohup' not in pidInfo:
            flag = True
        if flag:
            real_pid_arr.append(pid)
            processCount = processCount + 1
    return real_pid_arr


def stopWorker(modename):
    logger.info("stop model name= " + str(modename))
    worker_pid_array = get_real_pid_arr(modename)
    logger.info("found worker pids = " + str(worker_pid_array))
    for pid in worker_pid_array:
        cmd = "sudo kill -9 " + str(pid)
        os.system(cmd)

def change_base_model():
    models = get_oss_models()
    return gr.Dropdown.update(choices=models)

def train_ui():
    state = gr.State()

    # Draw layout
    notice = gr.Markdown(notice_markdown)
    with gr.Tab("训练"):
        with open('train_help.txt', 'r') as f:
            # 读取文件内容
            help_txt = f.readlines()
            help_txt_lines = ''
            for line in help_txt:
                help_txt_lines = help_txt_lines + line
        # help_txt_lines = ""
        help = gr.Textbox(label='训练提示：', value=help_txt_lines, max_lines=30, visible=True)

        with gr.Row():
            with gr.Column(scale=3):
                data_file = gr.File(label="数据文件")
            with gr.Column(scale=3):
                base_model = gr.Dropdown(label="基础模型",
                                         value=oss_models[0] if len(oss_models) > 0 else "",
                                         choices=oss_models)
                queue = gr.Dropdown(label="队列", value='kgb_llm', choices=['alimama_dolphin_llm', 'kgb_llm'])
                model_name = gr.Textbox(label="输出模型名称")
        with gr.Row():
            train = gr.Button(value='训练')
        with gr.Row():
            with gr.Column(scale=3):
                train_log = gr.Textbox(label="训练日志", lines=3, max_lines=20, show_label=True
                                       ).style(container=False)
            with gr.Column(scale=1):
                flush_train = gr.Button(value='刷新')

    with gr.Tab("部署"):
        with gr.Row():
            with gr.Column(scale=2):
                running_models = gr.Dropdown(choices=models, label="运行模型列表", interactive=True).style(container=False)
            with gr.Column(scale=1):
                stop_models = gr.Button(value="终止运行")
                stop_models.click(stopWorker, [running_models], [])
        with gr.Row():
            with gr.Column(scale=3):
                model_upload_name_1 = gr.Dropdown(label="模型名称",
                                         value=oss_models[0] if len(oss_models) > 0 else "",
                                         choices=oss_models)
            # with gr.Column(scale=3):
            #     port = gr.Textbox(label="端口号", placeholder="填写一个可用端口号", ).style(
            #         container=False)
            with gr.Column(scale=1):
                load_model = gr.Button(value='部署')
        with gr.Row():
            with gr.Column(scale=3):
                upload_log = gr.Textbox(label="部署日志", lines=3, max_lines=20, show_label=True
                                        ).style(container=False)
            with gr.Column(scale=1):
                with gr.Row():
                    model_upload_name = gr.Textbox(label="模型名称")
                with gr.Row():
                    flush_upload = gr.Button(value='刷新')
    train.click(train_process, inputs=[data_file, model_name, base_model, queue], outputs=train)
    running_models.change(flash_blur, None, running_models)
    load_model.click(upload_process, inputs=[model_upload_name_1], outputs=[load_model, model_upload_name])
    flush_train.click(flush_train_log, inputs=model_name, outputs=train_log)
    flush_upload.click(flush_upload_log, inputs=model_upload_name, outputs=upload_log)
    base_model.change(change_base_model,outputs=base_model)
    model_upload_name_1.change(change_base_model,outputs=model_upload_name_1)
    return state, base_model, running_models, model_upload_name_1

def load_demo():
    global oss_models, running_models
    oss_models = get_oss_models()
    base_model_update = gr.Dropdown.update(choices=oss_models, value=oss_models[0] if len(oss_models) > 0 else "", visible=True)
    running_models = get_model_list(controller_url)
    running_model_update = gr.Dropdown.update(choices=running_models, value=running_models[0] if len(running_models) > 0 else "", visible=True)

    return base_model_update, running_model_update, base_model_update

def build_demo():
    set_theme = adjust_theme()
    with gr.Blocks(
            title="MarketingGLM",
            theme=set_theme,
            css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)
        (state, base_model, running_models, model_upload_name_1) = train_ui()
        demo.load(load_demo, [], [base_model, running_models, model_upload_name_1])
    return demo


# share=False must be set to meet the data security policy of Alibaba
if __name__ == "__main__":
    gr.close_all()
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--controller-url", type=str, default="http://localhost:21001")
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument("--python_path", type=str, default="python3")
    parser.add_argument("--nebulactl_path", type=str, default="nebulactl")

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
    oss_models = get_oss_models()
    set_global_vars(args.controller_url, args.moderate, models, oss_models, args.python_path, args.nebulactl_path)
    refresh_models()
    logger.info(args)
    gr.close_all()
    demo = build_demo()
    demo.queue(
        concurrency_count=args.concurrency_count, status_update_rate=10, api_open=False
    ).launch(
        server_name=args.host, server_port=args.port, share=False, max_threads=200,
        auth=login, auth_message="请输入工号和密码"
        # server_name=args.host, server_port=args.port, share=True, max_threads=200
    )
