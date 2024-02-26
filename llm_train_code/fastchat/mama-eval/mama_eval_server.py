import argparse
import concurrent
import configparser
import datetime
import logging
import math
import os
import random
import sys
import threading
import time
import traceback
import uuid
from logging.handlers import TimedRotatingFileHandler

import requests
import json
import redis
from fastapi import FastAPI, Depends, Form, UploadFile
from fastapi.responses import *
from pydantic import BaseModel

app = FastAPI()

LOGDIR = "."
handler = None
class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.terminal = sys.stdout
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def __getattr__(self, attr):
        return getattr(self.terminal, attr)

    def write(self, buf):
        temp_linebuf = self.linebuf + buf
        self.linebuf = ""
        for line in temp_linebuf.splitlines(True):
            # From the io.TextIOWrapper docs:
            #   On output, if newline is None, any '\n' characters written
            #   are translated to the system default line separator.
            # By default sys.stdout.write() expects '\n' newlines and then
            # translates them so this is still cross platform.
            if line[-1] == "\n":
                encoded_message = line.encode("utf-8", "ignore").decode("utf-8")
                self.logger.log(self.log_level, encoded_message.rstrip())
            else:
                self.linebuf += line

    def flush(self):
        if self.linebuf != "":
            encoded_message = self.linebuf.encode("utf-8", "ignore").decode("utf-8")
            self.logger.log(self.log_level, encoded_message.rstrip())
        self.linebuf = ""
def build_logger(logger_name, logger_filename):
    global handler

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the format of root handlers
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    logging.getLogger().handlers[0].setFormatter(formatter)

    # Redirect stdout and stderr to loggers
    stdout_logger = logging.getLogger("stdout")
    stdout_logger.setLevel(logging.INFO)
    sl = StreamToLogger(stdout_logger, logging.INFO)
    sys.stdout = sl

    stderr_logger = logging.getLogger("stderr")
    stderr_logger.setLevel(logging.ERROR)
    sl = StreamToLogger(stderr_logger, logging.ERROR)
    sys.stderr = sl

    # Get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Add a file handler for all loggers
    if handler is None:
        os.makedirs(LOGDIR, exist_ok=True)
        filename = os.path.join(LOGDIR, logger_filename)
        handler = TimedRotatingFileHandler(
            filename, when="D", utc=True
        )
        handler.setFormatter(formatter)

        for name, item in logging.root.manager.loggerDict.items():
            print(name)
            print(item)
            if isinstance(item, logging.Logger):
                item.addHandler(handler)

    return logger
logger = build_logger("mama-eval", "mama.log")
import uvicorn
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Union, Dict, List

# app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


class Variables:
    def __init__(self):
        self.log_in_time = -1
        self.env = 'https://pre2-aurora.XXX-inc.com'
        self.redis_client = None
        self.config_path = os.path.dirname(os.path.abspath(__file__)) + '/config/redis_config.ini'
        self.redis_prefix = "eval:"
        self.redis_record_id_count_key = self.redis_prefix + "id_counter"
        self.redis_record_id_list = self.redis_prefix + "id_list"
        self.redis_record_hask_key_prefix = "eval_record_"
        self.redis_record_lock_name = "eval_lock"
        self.redis_tag_preix = "eval_tag_"
        self.redis_modify_lock_name = "add_or_update"
        self.redis_tag_meta_key = "eval_tag_meta"
        self.global_parse_json_model_name = ''
        self.global_parse_json_tag = ''
        self.global_invoke_thread_num = 3
        self.redis_async_job_list_key = "eval_async_job_list"
        self.redis_async_job_counter_key = "eval_async_job_counter"

        self.redis_async_job_log_prefix = "eval_async_log_"
        self.global_args = None


global_variables = Variables()


class User(BaseModel):
    username: str
    password: str


class Record(BaseModel):
    title: Union[str, None] = None
    prompt: Union[str, None] = None
    answer: Union[str, None] = None
    result: Union[str, None] = None
    expected: Union[str, None] = None
    model: Union[str, None] = None
    tag: Union[str, None] = None
    id: Union[str, None] = None


# utils
def initRedisClient():
    try:

        if not os.path.exists(global_variables.config_path):
            logger.error(global_variables.config_path + " file do not exist")
            return
        config = configparser.ConfigParser()
        config.read(global_variables.config_path)
        # 获取指定section下的option值
        redis_url = config.get('redis', 'url')
        redis_port = config.get('redis', 'port')
        redis_pwd = config.get('redis', 'pwd')
        redis_pool = redis.ConnectionPool(host=redis_url, password=redis_pwd, port=redis_port, decode_responses=True)
        global_variables.redis_client = redis.Redis(connection_pool=redis_pool)
    except Exception as e:
        logger.exception(e)
        return False, traceback.format_exception(e)
    logger.info("init redis cline done and successfully")
    return True, "ok"


@app.get("/")
async def index():
    return RedirectResponse("/index")


@app.get("/index")
async def login(request: Request):
    return templates.TemplateResponse(name="login.html", context={'request': request, })


@app.post("/login")
async def login(user: User):
    username = user.username
    password = user.password
    print(user.username)
    print(user.password)
    if verifyUser(username) and password == "admin":
        global_variables.log_in_time = time.time()
        return "success"
    else:
        return "error"


@app.get("/evaluate-dashboard")
async def dashboard(request: Request):
    if not checkLogInStatus():
        return RedirectResponse("/index")
    return templates.TemplateResponse("eval.html", context={'request': request, })


UPLOAD_DIR = os.path.dirname(os.path.abspath(__file__))


@app.post('/upload')
async def upload(file: UploadFile):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)  # 安全地获取文件名
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())

        res = get_async_job()
        flag = res.get("flag")
        if flag:
            log_id = res.get("log_id")
            start_async_by_thread(filepath, log_id)
        return res
    else:
        return {'flag': False, 'message': 'file format is not the expected！'}


# 允许上传的文件格式
ALLOWED_EXTENSIONS = set(['json'])


def process_func(filepath, log_id):
    try:
        res = parse_json(filepath, log_id)
        return res
    except Exception as e:
        logger.exception(e)
        return {
            'flag': True,
            'message': "parse json has error " + traceback.format_exception(e)
        }


def start_async_by_thread(filepath, log_id):
    t = threading.Thread(target=process_func, args=(filepath, log_id))
    t.start()


def get_async_job():
    try:
        log_id = global_variables.redis_client.incr(global_variables.redis_async_job_counter_key)
        global_variables.redis_client.lpush(global_variables.redis_async_job_list_key, str(log_id))
        return {
            "flag": True,
            "message": "submit current async eval job id =[ " + str(log_id) + "]",
            "log_id": str(log_id)
        }
    except Exception as e:
        logger.exception(e)
        return {
            "flag": False,
            "message": "submit async job has error"
        }


def get_current_timestamp_str():
    return datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')


def secure_filename(filename):
    return str(filename).split(".")[0] + "_" + get_current_timestamp_str() + "." + str(filename).split(".")[1]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def verifyUser(username):
    try:
        response = doAuroraRequest(global_variables.global_url_base + "/auroraAPI/ai-service/log-in/", {
            "authentication": {
                "project": "17560",
                "userId": username
            },
            "param": {

            }
        })
        # print(response)
        response_dict = json.loads(response.content.decode("utf8"))
        # print(response_dict)
        if response_dict['flag']:
            return True
        else:
            return False
    except Exception as e:
        traceback.format_stack(e)
        logger.exception(e)
        return False


def checkLogInStatus():
    if global_variables.log_in_time == -1 or (time.time() - global_variables.log_in_time) > 3600 * 12:
        return False
    else:
        return True


def parse_json(filepath, log_id):
    all = ''
    with open(filepath, "r") as f:
        all = f.read()
    redis_log_key = global_variables.redis_async_job_log_prefix + str(log_id)
    json_data = json.loads(all)
    if "tag" not in json_data and global_variables.global_parse_json_tag == '':
        return False, "`tag` do not find in upload file"
    tag_str = json_data.get('tag')
    data_list = json_data.get("data")
    if not isinstance(data_list, list):
        return False, '`data` must be a list, curreng is not'
    try:
        total_input = len(data_list)
        success_count = 0
        # for item in data_list:
        #     prompt_str = item.get("prompt")
        #     expected_answer = item.get("expected_answer")
        #     modelRequestParam = {
        #         "model": global_variables.global_parse_json_model_name,
        #         "prompt": prompt_str
        #     }
        #     flag, res = doModelRequest(modelRequestParam)
        #     if expected_answer == res:
        #         success_count = success_count + 1
        #     record = {
        #         "prompt": prompt_str,
        #         "answer": res,
        #         "result": expected_answer == res,
        #         "expected": expected_answer,
        #         "model": global_variables.global_parse_json_model_name,
        #         "tag": tag_str
        #     }
        #     do_redis_save_or_update(record)
        t0 = time.time()
        total, success_count, failed_count = multiThreadDoModelRequest(data_list, tag_str, global_variables.global_parse_json_model_name, redis_log_key, None)
        t1 = time.time()
        return {
            "flag": True,
            "message": "upload prompt total=[" + str(total_input) + "] success=[" + str(success_count) + "] failed=[" + str(failed_count) + "] cost [" + str(t1 - t0) + "]s"
        }
    except Exception as e:
        logger.exception(e)
        return {
            'flag': False,
            'message': "parse json has error " + traceback.format_exception(e)
        }
    finally:
        os.remove(filepath)


def processModelRequest(item: Dict, tag_str: str, model_name, id=None):
    prompt_str = item.get("prompt")
    expected_answer = item.get("expected_answer")
    title = item.get("title")
    modelRequestParam = {
        "model": model_name,
        "prompt": prompt_str
    }
    flag, res = doModelRequest(modelRequestParam)

    record = {
        "prompt": prompt_str,
        "answer": res,
        "title": title,
        "result": expected_answer == res,
        "expected": expected_answer,
        "model": model_name,
        "tag": tag_str
    }
    if id is not None and len(id) > 0:
        record["id"] = id

    do_redis_save_or_update(record)
    if expected_answer == res:
        return True,True, "ok"
    else:
        logger.error("expected" + expected_answer + " model res=" + res + " = " + str(expected_answer == res))
        if not flag:
            return False, False, res
        return False, True, "do not equal"


def multiThreadDoModelRequest(data_list: List, tag_str: str, model_name: str, redis_log_key: str, id_list=None):
    total_num = len(data_list)
    success = 0
    failed = 0
    index = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_arr = []
        for index in range(0, len(data_list)):
            item = data_list[index]
            id = None
            if id_list is not None:
                id = id_list[index]
            future_return = executor.submit(processModelRequest, item, tag_str, model_name, id)
            index = index + 1
            future_arr.append(future_return)
            msg ="[" + get_current_timestamp_str() + "] async job [" + redis_log_key + "] total records= [" + str(total_num) + "] current deal with [ " + str(index) + "] success count [ " + str(success) + "] success rate [" + "{:.2f}".format(success / total_num) + "] failed count [" + str(failed) + "] failed rate [" + " {:.2f}".format(failed / total_num) + "]"
            global_variables.redis_client.rpush(redis_log_key, msg)

        index = 0
        for future_return in concurrent.futures.as_completed(future_arr):
            index = index + 1
            data = future_return.result()
            retFlag = data[0]
            httpFlag = data[1]
            retMsg = data[2]
            if retFlag:
                success = success + 1
            else:
                failed = failed + 1
            msg ="[" + get_current_timestamp_str() + "]async job [" + redis_log_key + "] total records= [" + str(total_num) + "] current deal with [ " + str(index) + "] success count [ " + str(success) + "] success rate [" + "{:.2f}".format(success / total_num) + "] failed count [" + str(failed) + "] failed rate [" + " {:.2f}".format(failed / total_num) + "] "
            if not httpFlag:
                msg = msg + " failed msg = [ " + retMsg + "]"
            global_variables.redis_client.rpush(redis_log_key, msg)
        t1 = time.time()
        msg = "[" + get_current_timestamp_str() + "]async job [" + redis_log_key + "] total records= [" + str(total_num) + "] current deal with [ " + str(index) + "] success count [ " + str(success) + "] success rate [" + "{:.2f}".format(success / total_num) + "] failed count [" + str(failed) + "] failed rate [" + " {:.2f}".format(failed / total_num) + "]  total cost [" + "{:.2f}".format(t1 - t0) + "] s"
        global_variables.redis_client.rpush(redis_log_key, msg)
    return total_num, success, failed


def doAuroraRequest(full_url, param_dict, headers=None):
    if headers is None:
        headers = {'Connection': 'keep-alive', 'Accept': '*/*', 'Content-Type': 'application/json;charset=UTF-8'}
    response = requests.post(full_url, data=json.dumps(param_dict, ensure_ascii=False).encode("utf8"), headers=headers)
    return response


def do_redis_save_or_update(data_dict: dict):
    '''
    self.redis_record_id_count_key = self.redis_prefix + "id_counter"
        self.redis_record_id_list = self.redis_prefix + "id_list"
        self.redis_record_hask_key_prefix = "eval_record_"
        self.redis_record_lock_name = "eval_lock"
        self.redis_tag_preix = "eval_tag_"
        id
        tag

    '''
    try:
        getRedisLockAssure(global_variables.redis_modify_lock_name, lockTimeout=40)
        update_flag = False
        if data_dict.get("id") is not None and len(data_dict.get('id')) > 0:
            update_flag = True
        id = -1
        if update_flag:
            id = int(data_dict.get("id"))
        else:
            id = global_variables.redis_client.incr(global_variables.redis_record_id_count_key)
            global_variables.redis_client.lpush(global_variables.redis_record_id_list, str(id))
        record_key = global_variables.redis_record_hask_key_prefix + str(id)
        tag = data_dict.get("tag")
        tag_key = global_variables.redis_tag_preix

        if tag is not None and len(tag) > 0:
            tag_key = tag_key + tag
        else:
            tag_key = tag_key + "default"
        global_variables.redis_client.sadd(tag_key, str(id))
        global_variables.redis_client.sadd(global_variables.redis_tag_meta_key, tag_key.strip())
        for k, v in data_dict.items():
            global_variables.redis_client.hset(record_key, k, str(v))
        msg = 'add data successfully'
        if update_flag:
            msg = 'update data successfully'
        return {
            "flag": True,
            "message": msg
        }
    except Exception as e:
        logger.exception(e)
        return {
            'flag': False,
            'message': traceback.format_exception(e)
        }
    finally:
        releaseRedisLock(global_variables.redis_modify_lock_name)


def do_delete_record(record_id):
    try:
        global_variables.redis_client.lrem(global_variables.redis_record_id_list, 0, str(record_id))
        record_key = global_variables.redis_record_hask_key_prefix + str(record_id)
        global_variables.redis_client.delete(record_key)
        tag_key_set = global_variables.redis_client.smembers(global_variables.redis_tag_meta_key)
        for tag_key in tag_key_set:
            global_variables.redis_client.srem(tag_key, str(record_id))
    except Exception as e:
        logger.exception(e)
        return {
            "flag": False,
            "message": "delete failed, " + traceback.format_exception(e)
        }
    finally:
        releaseRedisLock(global_variables.redis_modify_lock_name)
    return {
        "flag": True,
        "message": "data deleted"
    }


def query_all(query_json: dict):
    offset = query_json.get("offset")
    limit = query_json.get("limit")
    if offset is None or limit is None:
        return {

        }
    total = global_variables.redis_client.llen(global_variables.redis_record_id_list)
    if offset >= total:
        offset = 0
        limit = -1
    if offset + limit >= total:
        if limit < total:
            offset = offset + 1
        limit = -1

    if offset > 1:
        offset = offset - 1
    if limit > 0:
        limit = limit - 1
    id_list = global_variables.redis_client.lrange(global_variables.redis_record_id_list, offset, limit)
    res = {}
    res['flag'] = True
    res['message'] = 'query data is ok'
    res['total'] = total
    tmp = []
    for record_id in id_list:
        record_key = global_variables.redis_record_hask_key_prefix + str(record_id)
        record_info = global_variables.redis_client.hgetall(record_key)
        arr = str(record_id).split("_")
        record_info['id'] = arr[len(arr) - 1]
        tmp.append(record_info)
    res['data'] = tmp
    logger.info(f'res= {res}')
    return res


@app.post("/api/save")
async def save_data(record: Record):
    print(record)
    prompt = record.prompt
    answer = record.answer
    if prompt is None or len(prompt) == 0 or answer is None or len(answer) == 0:
        return {"flag": False, "message": "may prompt or answer"}
    do_redis_save_or_update(record.__dict__)
    return "OK"


@app.get("/tags")
async def get_tags():
    return {
        "flag": True,
        "data": ['nlp2sql', 'marketing']
    }


def delete_log_func(id_list):
    for log_id in id_list:
        key = global_variables.redis_async_job_log_prefix + log_id
        res = global_variables.redis_client.delete(key)
        logger.info("delete async log " + key + " res = " + str(res))
        res = global_variables.redis_client.lrem(name=global_variables.redis_async_job_list_key, count=0, value=log_id)
        logger.info("delete list " + global_variables.redis_async_job_list_key + " res= [ " + str(res) + "]")


def start_delete_thread(id_list):
    t = threading.Thread(target=delete_log_func, args=(id_list,))
    t.start()


@app.get("/logs")
async def get_logs():
    id_list = global_variables.redis_client.lrange(global_variables.redis_async_job_list_key, 0, 9)
    len = global_variables.redis_client.llen(global_variables.redis_async_job_list_key)
    if len >= 10:
        remove_id_list = global_variables.redis_client.lrange(global_variables.redis_async_job_list_key, 9, -1)
        start_delete_thread(remove_id_list)

    return {
        "flag": True,
        "data": id_list
    }


class Log(BaseModel):
    log_id: Union[str, None] = None


@app.post("/api/get_log")
async def get_log_detail(log: Log):
    log_key = global_variables.redis_async_job_log_prefix + log.__dict__.get("log_id")
    logger.info("logkey " + log_key)
    list_log = global_variables.redis_client.lrange(log_key, 0, -1)
    msg = ""
    for item in list_log:
        msg = msg + item + "\n"
    return {
        "flag": True,
        "message": msg
    }


@app.get("/models")
def get_model_list():
    url = 'http://models-controller.XXX.com'
    if global_variables.global_args.env == 'prod':
        url = url + ':21001'
    controller_url = url
    ret = requests.post(controller_url + "/refresh_all_workers")
    assert ret.status_code == 200
    ret = requests.post(controller_url + "/list_models")
    models = ret.json()["models"]
    # models.sort(key=lambda x: priority.get(x, x))
    logger.info(f"Models: {models}")
    return {
        "flag": True,
        "data": models
    }


@app.post("/api/delete")
async def delete_data(record: Record):
    if record.id is None or len(record.id) == 0:
        return {
            'flag': False,
            'message': "record is empty"
        }
    else:
        return do_delete_record(record.id)

def do_re_run(id, tag, model):
    hash_key = global_variables.redis_record_hask_key_prefix + str(id)
    all_dict = global_variables.redis_client.hgetall(hash_key)
    item = {
        "prompt": all_dict.get("prompt"),
        "expected_answer": all_dict.get("expected"),
        "title": all_dict.get("title")
    }
    flag, ret, msg = processModelRequest(item, tag, model, id)
    return {
        "flag": flag,
        "message": msg
    }

@app.post("/api/rerun")
async def rerun(record: Record):
    id = record.id
    tag = record.tag
    model = record.model
    if id is None or len(id) == 0 or tag is None or len(tag) == 0 or model is None or len(model) == 0:
        return {
            'flag': False,
            'message': "record is empty"
        }
    else:
        return do_re_run(id,tag, model)

@app.post("/api/update")
async def update_data(record: Record):
    print(record.__dict__)
    return do_redis_save_or_update(record.__dict__)


def start_async_rerun_job(data_list, tag_str, model_str, redis_log_key, id_list):
    t = threading.Thread(target=multiThreadDoModelRequest, args=(data_list, tag_str, model_str, redis_log_key, id_list))
    t.start()


@app.post("/api/run")
async def update_data(record: Record):
    tag_str = record.__dict__.get('tag')
    model_str = record.__dict__.get('model')
    if tag_str is None or len(tag_str) == 0:
        return {
            "flag": False,
            "message": "no tag is selected"
        }
    key = global_variables.redis_tag_preix + tag_str
    id_list_set = global_variables.redis_client.smembers(key)
    data_list = []
    id_list = []
    for id in id_list_set:
        hash_key = global_variables.redis_record_hask_key_prefix + id
        all_dict = global_variables.redis_client.hgetall(hash_key)
        data_list.append({
            "prompt": all_dict.get("prompt"),
            "expected_answer": all_dict.get("expected"),
            "title": all_dict.get("title")
        })
        id_list.append(id)
    res = get_async_job()
    flag = res.get("flag")
    if flag:
        log_id = res.get("log_id")
        redis_log_key = global_variables.redis_async_job_log_prefix + str(log_id)
        start_async_rerun_job(data_list, tag_str, model_str, redis_log_key, id_list)
    return res
    #     expected_answer = item.get("expected_answer")


@app.post("/set_model")
async def set_model(record: Record):
    global_variables.global_parse_json_model_name = record.__dict__.get('model')
    return {
        "flag": True,
        "msg": "set json parse model =[ " + global_variables.global_parse_json_model_name + " ]"
    }


@app.post("/set_tag")
async def set_tag(record: Record):
    global_variables.global_parse_json_tag = record.__dict__.get('tag')
    return {
        "flag": True,
        "msg": "set json parse model =[ " + global_variables.global_parse_json_tag + " ]"
    }


class QueryParam(BaseModel):
    page: Union[int, None] = 1
    page_size: Union[int, None] = 10


@app.post("/api/table")
async def get_table(queryParam: QueryParam):
    page = queryParam.page
    page_size = queryParam.page_size
    offset = max(0, page_size * (page - 1))
    limit = page * page_size
    print(page)
    print(page_size)
    print(offset)
    print(limit)
    res = query_all({
        'offset': offset,
        'limit': limit
    })
    return res


def doModelRequest(request_dict: Dict):
    """

    output:
    {
  "id": "3vnKaKhQgNPfsWt7ZgDMb6",
  "object": "chat.completion",
  "created": 1685439836,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "select thedate, sum(f_charge) as f_charge from bp_report.rpt_ad_xgonebp_offline_days_di where  member_id='7123456'  and thedate >= toStartOfMonth(today()) group by thedate order by thedate desc"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": null
  }
    """
    sleep_time = random.randint(1, 2)
    time.sleep(sleep_time)
    params = {}
    params['model'] = request_dict.get("model")
    prompt = request_dict.get("prompt")
    params['messages'] = [{'role': 'user', 'content': prompt}]
    logger.info("models request " + str(params))
    url = 'http://ai-models-provider.XXX.com'
    if  global_variables.global_args.env == "prod":
        url = url + ":8100"
    res = requests.post(url + "/v1/chat/completions", data=json.dumps(params, ensure_ascii=False).encode("utf8"))
    data = None
    if res.status_code == 200:
        data = res.json()
        out_str = ''
        try:
            out_str = data['choices'][0]['message']['content']
        except Exception as e:
            logger.exception(e)
            try:
                out_str = data['detail']['msg']
                return False, out_str
            except Exception as e1:
                logger.exception(e1)
                out_str = 'get result has error'
                return False, out_str
        return True, out_str
    else:
        logger.error(res.content)
        return False, "http error" + str(res.content)


def getRedisLockAssure(lockName, lockTimeout=5):
    ret = getRedisLock(lockName, lockTimeout=lockTimeout)
    while not ret:
        ret = getRedisLock(lockName, lockTimeout=lockTimeout)
        if not ret:
            logger.info("Can't get lock! Ret: {}, retry in 10 second".format(ret))
            time.sleep(3)
        else:
            break


def getRedisLock(lockName, acquireTimeout=3, lockTimeout=2):
    """
        基于 Redis 实现的分布式锁
        :param lockName: 锁的名称
        :param acquireTimeout: 获取锁的超时时间，默认 3 秒
        :param lockTimeout: 锁的超时时间，默认 2 秒
        :return:
        """

    identifier = str(uuid.uuid4())
    lockDesc = "mama_eval_system_lock_" + lockName
    logger.info('use ' + lockDesc + ' to get redis lock')
    lock_timeout = int(math.ceil(lockTimeout))

    end = time.time() + acquireTimeout

    while time.time() < end:
        # 如果不存在这个锁则加锁并设置过期时间，避免死锁
        if global_variables.redis_client.set(lockDesc, identifier, ex=lock_timeout, nx=True):
            return identifier
        time.sleep(0.001)

    return False


def releaseRedisLock(lockName):
    """
        释放锁
        :param lockName: 锁的名称
        :return:
        """
    # python中redis事务是通过pipeline的封装实现的
    lockDesc = "mama_eval_system_lock_" + lockName
    ret = global_variables.redis_client.delete(lockDesc)
    logger.info('global_redis_alive_client().delete ' + lockDesc + ' result = ' + str(ret))
    if ret == 0:
        return True
    else:
        return False


if __name__ == "__main__":
    initRedisClient()
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=25000)
    parser.add_argument("--env", type=str, default="pre")
    args = parser.parse_args()
    global_variables.global_args = args
    if args.env == 'pre':
        global_variables.global_url_base = 'https://pre2-aurora.XXX-inc.com'
    elif args.env == 'dev':
        global_variables.global_url_base = 'https://pre2-aurora.XXX-inc.com'
    else:
        global_variables.global_url_base = 'https://aurora2.XXX-inc.com'
    uvicorn.run(app, host=args.host, port=args.port)
