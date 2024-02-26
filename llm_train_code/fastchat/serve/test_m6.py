# import gradio as gr
# import pandas as pd
# from vega_datasets import data
#
# stocks = data.stocks()
#
# simple = pd.DataFrame({
#     'a': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'],
#     'b': [28, 55, 43, 91, 81, 53, 19, 87, 52]
# })
#
# data=[["Rudra",1,2],
#       ["Rudra",2,3],
#       ["Rudra",3,4],
#       ["Rudra",4,5],
#       ["Rudra2", 1, 2],
#       ["Rudra2", 2, 4],
#       ["Rudra2", 3, 5],
#       ["Rudra2", 4, 6]
#      ]
# data_f = pd.DataFrame(data, columns=["Name","time","val"])
# with gr.Blocks() as demo:
#     disable_plot = gr.BarPlot(
#         data_f,
#         x="time",
#         y="val",
#         title="Simple Bar Plot with made up data",
#         tooltip=['Name', 'time', 'val'],
#         group_title="",
#         # group="Name",
#         visible=True
#     )
#
#     line_plot1  = gr.LinePlot(
#         stocks,
#         x="date",
#         y="price",
#         color="symbol",
#         color_legend_position="bottom",
#         title="Stock Prices",
#         tooltip=['date', 'price', 'symbol'],
#         height=300,
#         width=500
#     )
#
#     line_plot = gr.LinePlot(
#             data_f,
#             x="time",
#             y="val",
#             color="Name",
#             color_legend_position="bottom",
#             title="Stock Prices",
#             tooltip=['Name', 'time', 'val'],
#             height=300,
#             width=500
#         )
#
# demo.launch()
import json
import requests
import time

worker_addr = 'http://mama-m6.alimama.com/worker_generate_stream'
headers = {'Content-Type': 'application/json'}
pload = { "model": "nebula_m6", "prompt": "请根据工具描述与用户输入来确定是否需要调用工具，若需要调用工具且用户输入了合理的参数请以Tool开头输出一段JSON格式的包含特定工具id与对应参数的工具信息，否则请以Assistant开头输出正常回答，或以ToolParam开头引导用户描述参数。\n工具描述: diagnosis，参数为单元id-adgroup_id与日期-date，可诊断展现、点击相关投放效果问题；kr，参数为单元id-adgroup_id，可进行关键词推荐。\n\nHuman: 为什么我的计划到5月4号一直没有展现，单元ID：4069595657\n\n", "temperature": 0.7, "max_new_tokens": 512, "stop": "</s>" }
pload = { "model": "nebula_m6", "prompt": "请根据工具描述与用户输入来确定是否需要调用工具，若需要调用工具且用户输入了合理的参数请以Tool开头输出一段JSON格式的包含特定工具id与对应参数的工具信息，否则请以Assistant开头输出正常回答，或以ToolParam开头引导用户描述参数。\n工具描述: diagnosis，参数为单元id-adgroup_id与日期-date，可诊断展现、点击相关投放效果问题；kr，参数为单元id-adgroup_id，可进行关键词推荐。\n\n Human: 为什么我的计划到5月4号一直没有展现，单元ID：4069595657\n\n", "temperature": 0.7, "max_new_tokens": 512, "stop": "</s>" }

response = requests.post(
worker_addr,
headers=headers,
json=pload,
stream=True,
timeout=2000,
)
# logger.info(response)
for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):

    if chunk:
        data = json.loads(chunk.decode())
        output = data["text"].replace('\n', ' ')
        print(output)
# return
time.sleep(0.02)
