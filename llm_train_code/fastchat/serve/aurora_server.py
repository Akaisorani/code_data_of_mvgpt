import datetime
import json
import time
import requests
import re

from fastchat.serve.dolphin import get_kr_info


def execute_dolphin_sql(sql):
    start_time = time.time()
    # host = host_env_dict.get(app.config.get('ENV', default_env))
    authentication = {'accessId': 'K3LmR7ne0MQLyMOV', 'token': '054WHnUaeWAKyLqltLBFanyatea2TQnw', 'userId': '329277'}
    headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    executeSqlParamMap = {'nodeId': 2629, 'cluster': 3, 'engine': 'hologres', 'sql': sql}
    params = {'param': executeSqlParamMap, 'authentication': authentication}
    print(params)
    response = requests.post('http://aurora2.XXX-inc.com' + '/auroraAPI/auroSql/executeNl2Sql',
                             data=json.dumps(params), headers=headers)
    # logger.info("execute dolphin sql cost " + str(time.time() - start_time))
    if response.status_code != 200:
        err_msg = "call dolphin error, status code is " + str(response.status_code)
        # logger.error(err_msg)
        raise Exception(err_msg)
    json_entity = json.loads(response.text)
    if not json_entity['success']:
        err_msg = "call dolphin error, error message " + json_entity['message']
        # logger.error(err_msg)
        raise Exception(err_msg)
    taskId = json_entity['data']['taskIds'][0]
    jobId = json_entity['data']['jobId']
    executeSqlParamMap = {'jobId': jobId, 'taskId': taskId}
    params = {'param': executeSqlParamMap, 'authentication': authentication}
    time.sleep(3)
    response = requests.post('http://aurora2.XXX-inc.com' + '/auroraAPI/auroSql/getResult', data=json.dumps(params),
                             headers=headers)
    if response.status_code != 200:
        err_msg = "call dolphin error, status code is " + str(response.status_code)
        # logger.error(err_msg)
        raise Exception(err_msg)
    json_entity = json.loads(response.text)
    if not json_entity['success']:
        err_msg = "call dolphin error, error message " + json_entity['message']
        # logger.error(err_msg)
        raise Exception(err_msg)
    data = json_entity['data']

    return json.dumps(data)

def send_tool_request(request, serviceName, functionName):
    authentication = {'accessId': 'K3LmR7ne0MQLyMOV', 'token': '054WHnUaeWAKyLqltLBFanyatea2TQnw', 'userId': '329277'}
    params = {'request': request, 'serviceName': serviceName, 'functionName': functionName, 'authentication': authentication}
    headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    response = requests.post('http://aurora2.XXX-inc.com' + '/auroraAPI/ai-service/fass-service', data=json.dumps(params), headers=headers)
    if response.status_code != 200:
        err_msg = "call aurora error, status code is " + str(response.status_code)
        raise Exception(err_msg)
    json_entity = json.loads(response.text)
    if not json_entity['success']:
        err_msg = "call aurora error, error message " + json_entity['message']
        raise Exception(err_msg)
    result = json_entity['data']
    return result

def get_prompt_trans(scene, prompt):
    authentication = {'accessId': 'K3LmR7ne0MQLyMOV', 'token': '054WHnUaeWAKyLqltLBFanyatea2TQnw', 'userId': '329277'}
    params = {'scene': scene, 'prompt': prompt, 'authentication': authentication}
    headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    response = requests.post('http://pre2-aurora.XXX-inc.com' + '/auroraAPI/copilot/fass-service', data=json.dumps(params), headers=headers)
    # response = requests.post('http://pre2-aurora.XXX-inc.com' + '/auroraAPI/ai-service/fass-service', data=json.dumps(params), headers=headers)
    if response.status_code != 200:
        err_msg = "call aurora error, status code is " + str(response.status_code)
        raise Exception(err_msg)
    json_entity = json.loads(response.text)
    if not json_entity['success']:
        err_msg = "call aurora error, error message " + json_entity['message']
        raise Exception(err_msg)
    result = json_entity['data']
    return result

def execute_tool_request(request):
    json_entity = json.loads(request)
    tool_id = json_entity['tool_id']
    params = json_entity['params']
    tool_request = {}
    if tool_id == 'diagnosis':
        adgroup_id = params['adgroup_id']
        dt = params.get('date')
        now_ = datetime.datetime.now()
        dt_regx = re.compile(r"[-|\\/\.]")
        try:
            dt_split = list(filter(lambda x:len(x)>0, dt_regx.split(dt)))
            if len(dt_split) == 2:
                ds = datetime.datetime.strptime(".".join([str(now_.year), *dt_split]), "%Y.%m.%d")
            elif len(dt_split) == 3:
                ds = datetime.datetime.strptime(".".join(dt_split), "%Y.%m.%d")
            elif len(dt) == 8:
                ds = datetime.datetime.strptime(dt, "%Y%m%d")
            else:
                ds = now_
        except:
            ds = now_
        ds = ds.strftime('%Y%m%d')
            
        tool_request['ds'] = ds
        tool_request['adgroupId'] = adgroup_id
        tool_request['requestType'] = 'ImpPlungeSop'
        result = send_tool_request(json.dumps(tool_request), 'fg-XXX-app-120', 'CmopSmartSop')
        return result
    if tool_id == 'kr':
        adgroup_id = params['adgroup_id']
        title, cate_list = get_kr_info(adgroup_id)
        ad_info = {}
        ad_info['categoryId'] = cate_list
        ad_info['title'] = title
        ad_info['adgroupId'] = adgroup_id
        tool_request['ad_info'] = ad_info
        parameter = {}
        parameter['pipeline'] = 'wdcb'
        parameter['maxKeywordCount'] = 10
        parameter['rankRule'] = 'default'
        parameter['from'] = 'offline'
        bagIdList = []
        bagIdList.append(2)
        parameter['bagIdList'] = bagIdList
        tool_request['parameter'] = parameter

        result = send_tool_request(json.dumps(tool_request, ensure_ascii=False), 'fg-XXX-app-120', 'Cmopengine')
        return result

if __name__ == '__main__':
    print(datetime.datetime.now().strftime('%Y%m%d'))
    s = '{"tool_id": "kr", "params": {"adgroup_id": "4310156998", "date": ""}}'.replace(', ', ',')
    print(s)
    print(execute_tool_request(s))
    print(get_prompt_trans("nl2sql", "欧莱雅品牌"))