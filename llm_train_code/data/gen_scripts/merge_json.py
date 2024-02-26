import json
import os

folderPath="./json/"
out_file_path="all.json"

all_data=[]
cnt = 0
for root, dirs, files in os.walk(folderPath):
    for file in files:
        file_path = os.path.join(root, file)
        if not file_path.endswith(".json"):
            continue
        print("merge file: "+file_path)
        with open(file_path, 'r') as f:
            table1 = json.load(f)
        for item in table1:
            all_data.append({'id':str(cnt),"conversations": item['conversations']})
            cnt += 1

with open(out_file_path, "w") as f:
    json.dump(all_data, f,ensure_ascii=False)

        