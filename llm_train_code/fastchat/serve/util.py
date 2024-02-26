import json
import time
import requests
import gradio as gr
import pandas as pd
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
    response = requests.post('http://aurora2.alibaba-inc.com' + '/auroraAPI/auroSql/executeNl2Sql',
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
    response = requests.post('http://aurora2.alibaba-inc.com' + '/auroraAPI/auroSql/getResult', data=json.dumps(params),
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

def sendChatRecords(input, output, modelName, userId=None, tag=None):
    start_time = time.time()
    # host = host_env_dict.get(app.config.get('ENV', default_env))
    authentication = {'accessId': 'K3LmR7ne0MQLyMOV', 'token': '054WHnUaeWAKyLqltLBFanyatea2TQnw', 'userId': '329277'}
    headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    executeSqlParamMap = {'input': input, 'output': output, 'modelName': modelName}
    if(tag != None):
        executeSqlParamMap['sign'] = tag
    if(userId != None):
        executeSqlParamMap['userId'] = userId
    params = {'param': executeSqlParamMap, 'authentication': authentication}
    print(params)
    response = requests.post('http://pre2-aurora.alibaba-inc.com' + '/auroraAPI/ai-service/save-talk',
                             data=json.dumps(params), headers=headers)
    # logger.info("execute dolphin sql cost " + str(time.time() - start_time))
    if response.status_code != 200:
        err_msg = "call aurora sendChatRecords error, status code is " + str(response.status_code)
        print(err_msg)

def execute_tool(input):
    params = {'input': input, 'type': 'nl2tool'}
    response = requests.post('http://11.167.74.132:81/autogpt', data=params)
    return response.text

def execute_dolphin_sql(sql):
    start_time = time.time()
    print("start execute dolphin sql: " + sql.replace('\n', ' '))
    params = {"dbType": "dolphin", "sql": sql}
    headers = {"accessId": "6FMEl0doocC8C6IP", "accessKey": "29RAHzFyKne7Ei3Dg3eZCFeXufsvy25T"}

    response = requests.post("http://report-jdbc-cn-zhangbei.dolphin.alimama.com/api/tasks/insight", params=params,headers=headers)
    print("execute dolphin sql cost " + str(time.time() - start_time))
    if response.status_code != 200:
        err_msg = "call dolphin error, status code is " + str(response.status_code)
        print(err_msg)
        raise Exception(err_msg)
    json_entity = json.loads(response.text)
    if not json_entity['success']:
        err_msg = "call dolphin error, error message " + json_entity['message']
        print(err_msg)
        raise Exception(err_msg)
    # list list结构
    return json_entity['result']

def execute_ck_sql(sql):
    start_time = time.time()
    print("start execute ck sql: " + sql.replace('\n', ' '))

    query = sql

    auth = ("default", "ck@401618")
    url = f'https://ai.alimama.com'
    response = requests.post(url, data=query, auth=auth)
    sql_result = response.content.decode("utf8")
    print("execute ck sql cost:" + str(time.time() - start_time))
    data_list = [line.split('	') for line in sql_result.split('\n') if line.strip()]
    columns = [column_str.strip().split("	") for column_str in sql_result.strip().split("\n")]
    result_list = [list(row) for row in zip(*columns)]

    return data_list, result_list

def datas_to_table_html(data):
    df = pd.DataFrame(data[1:], columns=data[0])
    table_style = """<style> 
        table{border-collapse:collapse;width:60%;height:80%;margin:0 auto;float:left;border: 1px solid #007bff; background-color:#CFE299}th,td{border:1px solid #ddd;padding:3px;text-align:center}th{background-color:#C9C3C7;color: #fff;font-weight: bold;}tr:nth-child(even){background-color:#7C9F4A}tr:hover{background-color:#333}
     </style>"""
    html_table = df.to_html(index=False, escape=False)

    html = f"<html><head>{table_style}</head><body>{html_table}</body></html>"

    return html.replace("\n", " ")


def generate_markdown_table(data):
    """\n    生成 Markdown 表格\n    data: 一个包含表头和表格内容的二维列表\n"""
    # 获取表格列数
    num_cols = len(data[0])
    # 生成表头
    header = "| "
    for i in range(num_cols):
        header += data[0][i] + " | "

    # 生成分隔线
    separator = "| "
    for i in range(num_cols):
        separator += "--- | "

    # 生成表格内容
    content = ""
    for row in data[1:]:
        content += "| "
        for i in range(num_cols):
            content += str(row[i]) + " | "
        content += "\n"

    # 合并表头、分隔线和表格内容
    table = "\n" + header + "\n" + separator + "\n" + content

    return table

def getModelReturn(prompt):
    plot = gr.BarPlot.update(
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
    # if '帮助' in prompt or 'help' in prompt:
    #     print('prompt:' + prompt)
    #     with open(r'help.txt', 'r') as help_file:
    #         message = help_file.read()
    #         print('message:' + message)
    #     return message, '', plot

    sql_result = ''
    message = prompt
    if 'select' in message:
        print('message:' + str(message))
        message = message.replace('theDate', 'thedate')
        message = message.replace('thedate', 'toDate(toString(thedate))')
        try:
            sql_result, result_list = execute_ck_sql(message)
            sql_result = datas_to_table_html(sql_result)
            sql_result = 'sql执行结果：\n' + sql_result
            message = '```sql\n' + message + "\n```"
            print("result_list[0]:" + str(result_list[0]))
            print("result_list[1]:" + str(result_list[1]))
            if len(result_list) == 2:
                plot_data = pd.DataFrame({
                    '日期': result_list[0],
                    '值': result_list[1]
                })
                plot = gr.BarPlot.update(
                    plot_data,
                    x="日期",
                    y="值",
                    title="数据可视化展示",
                    tooltip=['日期', '值'],
                    visible=True
                )
        except Exception as e:
            print('execute sql error.')
            print(e)
    return message, sql_result, plot



if __name__ == '__main__':
    # print(execute_dolphin_sql("select thedate ,sum(alipay_cnt) from bp_dmp.rpt_amp_sap_item_action_stat_1d where cate_id  = 201683515 and toDate(toString(thedate)) > '20230201' group by thedate;"))
    # print(getModelReturn('analyticai-13b-mama_sql_v508_v4', 'who are you？'))
    # with open(r'/Users/zhengjianhui/PycharmProjects/mama-ai/help.txt', 'r') as out_file:
    #     message = out_file.read()
    #     print(message)
    print(execute_ck_sql('select thedate,sum(alipay_amt) as alipay_amt from bp_dmp_rpt_amp_sap_item_action_stat_1d where  brand_id=20068  and toDate(toString(thedate)) >= date_sub(Month, 6, today()) group by thedate limit 2;'))