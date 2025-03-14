from datasets import load_dataset
import os
import json

dataset_root="./"
data_files = {
    "train": os.path.join(dataset_root, "mv-train3.jsonl"),
    # "validation": os.path.join(dataset_root, "mv-validation.jsonl"),
    "test": os.path.join(dataset_root, "mv-test3.jsonl"),
}
dst_data_files = {
    "train": os.path.join(dataset_root, "data_train.json"),
    # "validation": os.path.join(dataset_root, "mv-validation.jsonl"),
    "test": os.path.join(dataset_root, "data_test.json"),
}

sql_dataset=load_dataset("json", data_files=data_files)


def convert_text2conversion(line):
    text=line["text"]
    spl_pos=text.rfind('-- Expression:')
    prpt=text[:spl_pos+len('-- Expression:')].strip()
    label=text[spl_pos+len('-- Expression:'):].strip()

    conversations=[
        {
            "from": "human",
            "value": prpt
        },
        {
            "from": "gpt",
            "value": label
        }
    ]

    return {"conversations":conversations}


sql_dataset["train"]=sql_dataset["train"].map(convert_text2conversion, remove_columns=["text"])
sql_dataset["test"]=sql_dataset["test"].map(convert_text2conversion, remove_columns=["text"])

sql_dataset["train"].to_json(dst_data_files["train"])
sql_dataset["test"].to_json(dst_data_files["test"])


list_train=[{"id":f"identity_{index}", "conversations":conv} for index, conv in enumerate(sql_dataset["train"].to_dict()['conversations'])]
list_test=[{"id":f"identity_{index}", "conversations":conv} for index, conv in enumerate(sql_dataset["test"].to_dict()['conversations'])]

with open(dst_data_files["train"], "w") as fp:
    json.dump(list_train, fp)

with open(dst_data_files["test"], "w") as fp:
    json.dump(list_test, fp)




    


