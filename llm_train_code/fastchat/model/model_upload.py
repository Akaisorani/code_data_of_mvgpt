import configparser
import os
import random
import time

import subprocess
import threading
import logging
import argparse
from fastchat.utils import (
    build_logger,
    server_error_msg,
    violates_moderation,
    moderation_msg,
)
logger = build_logger("model_upload", "model_upload.log")


def execute_cmd_with_error_timeout(cmd, timeout=60):
    proc = None
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (outs, errs) = proc.communicate(timeout=timeout)
    except Exception as e:
        return -9, '', 'timed out after ' + str(timeout) + ' seconds'
    return proc.returncode, outs.decode("utf8"), errs.decode("utf8")


def executeCmdWithError(cmd, timeout=60):
    ret, out, error = execute_cmd_with_error_timeout(cmd, timeout)
    return ret, out, error

def combinations(items, n):
    """\n    从items中选择n个元素的所有组合方式\n    """
    if n == 0:
        return [[]]
    res = []
    for i in range(len(items)):
        for c in combinations(items[i+1:], n-1):
            res.append([items[i]] + c)
    return res

def random_combination(items, n):
    """\n    从items中随机选择n个元素的组合方式\n    """
    combs = combinations(items, n)
    rand_index = random.randint(0, len(combs)-1)
    return combs[rand_index]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    config = configparser.ConfigParser()
    config.read('train_mdl/train_oss.ini')
    # 获取指定section下的option值
    oss_id = config.get('oss', 'oss_id')
    oss_key = config.get('oss', 'oss_key')
    parser.add_argument("--id", type=str, default=oss_id)
    parser.add_argument("--key", type=str, default=oss_key)
    parser.add_argument("--host", type=str, default="oss-accelerate.XXXcs.com")
    parser.add_argument("--oss_path", type=str, default="oss://faeet2/ai_service/models/analyticai-7b-mama_sql_v424/")
    parser.add_argument("--model_path", type=str, default="/home/admin/mama-ai/models/analyticai-7b-mama_sql_v424/")
    parser.add_argument("--port", type=int, default="21009")
    parser.add_argument("--python_path", type=str, default="/home/wangyin.yx/conda38/bin/python3")
    global_metric = parser.parse_args()
    oss_path = global_metric.oss_path
    modelName = oss_path.rstrip('/').split('/')[-1]
    model_path = os.getcwd() + '/models_in/' + modelName
    model_out_path = os.getcwd() + '/models/' + modelName
    print(model_path)
    downLoadCmd = "sudo osscmd --id={} --key={} --host={} downloadtodir {}  {} --replace=true --thread_num=40".format(
        global_metric.id, global_metric.key, global_metric.host,
        global_metric.oss_path,
        model_path
    )
    logger.info("downLoadCmd= " + downLoadCmd)
    print("downLoadCmd= " + downLoadCmd)
    t0 = time.time()
    res, _, error = executeCmdWithError(downLoadCmd, timeout=8000)
    if res == 0:
        logger.info("download {} successfully , time cost {} s".format(modelName,
                                                                    time.time() - t0))
    if res != 0:
        logger.info("download failed , downloaded binary files can not trusted, clean up , error_msg " + str(error))

    transCmd = global_metric.python_path +" -m fastchat.model.convert_fp16 --in {} --out {} ".format(
        model_path,
        model_out_path
    )
    logger.info("transCmd= " + transCmd)
    print("transCmd= " + transCmd)
    to = time.time()
    res, _, error = executeCmdWithError(transCmd, timeout=1200)
    if res == 0:
        logger.info("transCmd {} successfully , time cost {} s".format(modelName,
                                                                    time.time() - t0))
    if res != 0:
        logger.info("download failed , downloaded binary files can not trusted, clean up , error_msg " + str(error))

    # start worker
    items = random.sample(range(8), 8)
    gpuIndexList = random_combination(items,4)
    gpuIndexStrList = [str(i) for i in gpuIndexList]
    indexStr = ",".join(gpuIndexStrList)
    prefixCuda = 'CUDA_VISIBLE_DEVICES=' + indexStr
    startWorkerCmd = prefixCuda+ " nohup " + global_metric.python_path + " -m fastchat.serve.model_worker --model-path {} --num-gpus 4 --host 0.0.0.0 --port {} --worker-address http://0.0.0.0:{} >> log/{}_upload.log 2>&1 &".format(
        model_out_path,
        global_metric.port,
        global_metric.port,
        modelName
    )

    logger.info("startWorkerCmd= " + startWorkerCmd)
    print("startWorkerCmd= " + startWorkerCmd)
    to = time.time()
    os.system(startWorkerCmd)