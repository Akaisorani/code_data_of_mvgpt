# -*- coding: utf-8 -*-

import json

data_list = []
with open('dev.json', 'r') as f:
    # 从文件中读取JSON数据并将其转换为Python对象
    data = json.load(f) 
    #print(len(data))
    for elem in data:
        if "simple" == elem["difficulty"]:

             #print(elem['difficulty'])
             data_list.append(elem)
#"difficulty": "simple"
#data_list = data[0:1]
#print(len(data_list))
#print(json.dumps(data_list))
with open("dev_simple_gold.sql", "w") as f2:
    for data in data_list:
        f2.write(data['SQL'].encode("utf-8")+"\t" +  data["db_id"].encode("utf-8") + "\n")
