import csv
import os
import pandas as pd
import random
from datasets import load_dataset
import re
import time

src_file="./data/mv_exp_ts_cleaned_231009.csv"
dst_train_file="./data/mv-train4.jsonl"
# dst_validation_file="./data/mv-validation.jsonl"
dst_test_file="./data/mv-test4.jsonl"

# df.columns=['timestamp', 'member_id', 'exp']
sql_dataset=load_dataset("csv", data_files=src_file, sep="#")

# use 300000 entries for debug
# sql_dataset["train"]=sql_dataset["train"][:300000]
# print(sql_dataset)


sql_dataset["train"]=sql_dataset["train"].map(lambda x: {'exp': x['exp'].replace('\t',' ').replace('new_XXX','nd').replace('XXX_XXX_dp','tdd')})
sql_dataset["train"]=sql_dataset["train"].filter(lambda x: len(x['exp'])<=1000)
# sql_dataset["train"]=sql_dataset["train"].filter(lambda x: 'euclidean_distance' not in x['exp'])

total_examples=len(sql_dataset["train"])
train_examples=total_examples*5//6
train_rows=train_examples//5
example_num_each_row=5
# validation_rows=300
test_examples=total_examples-train_examples
test_rows=test_examples//5

sql_dataset["train"]=sql_dataset["train"].sort('timestamp')
sql_dataset=sql_dataset["train"].train_test_split(test_size=test_examples/total_examples, shuffle=False)

# do extract tables.columns     pattern: nd.balabala.balabala
pattern=re.compile(r'nd\.[.|\w]+')
def extract_identifiers(exp):
    identifiers_lis=pattern.findall(exp)
    identifiers_lis=list(set(identifiers_lis))
    identifiers_lis.sort()
    return identifiers_lis

# map cluster id
def add_identifiers(line):
    identifiers_lis=extract_identifiers(line['exp'])
    identifiers_s=" ".join(identifiers_lis)
    return {"idtfr": identifiers_s}

# first add a label of identifiers, then do cluster with identifiers
sql_dataset["train"]=sql_dataset["train"].map(add_identifiers, num_proc=64)
sql_dataset["test"]=sql_dataset["test"].map(add_identifiers, num_proc=64)

sql_dataset["train"]=sql_dataset["train"].filter(lambda x: x['idtfr'].strip() and x['idtfr'].strip()!="nd.crowd_materialize_view_for_XXX.crowd_id")
sql_dataset["test"]=sql_dataset["test"].filter(lambda x: x['idtfr'].strip() and x['idtfr'].strip()!="nd.crowd_materialize_view_for_XXX.crowd_id")


distinct_num1=len(list(set(sql_dataset["train"]['idtfr'])))
distinct_num2=len(list(set(sql_dataset["test"]['idtfr'])))
print(len(sql_dataset["train"]), distinct_num1)
print(len(sql_dataset["test"]), distinct_num2)

# cnt={}
# for line in sql_dataset["train"]:
#     idtfr=line['idtfr']
#     # if idtfr=='':
#     #     print(line['exp'])
#     if idtfr in cnt:
#         cnt[idtfr]+=1
#     else:
#         cnt[idtfr]=1

# lis=list(cnt.items())
# lis.sort(key=lambda x: x[1], reverse=True)
# print(lis[:10])
# cnt_v=[x[1] for x in lis]
# print("count 1",cnt_v.count(1))
# cnt5=0
# for x in cnt_v:
#     if x<5: cnt5+=1
# print("count <5",cnt5)
# print(cnt_v[-30:])

# for idtfr, cnt in lis[:10]:
#     print(idtfr)
#     print(cnt)

# exit()

# begin sort
print("begin sort idtfr", flush=True)
sql_dataset["train"]=sql_dataset["train"].sort('idtfr')
sql_dataset["test"]=sql_dataset["test"].sort('idtfr')
print("end sort idtfr", flush=True)

def build_cnt(dataset):
    cnt={}
    for line in dataset:
        idtfr=line['idtfr']
        if idtfr in cnt:
            cnt[idtfr]+=1
        else:
            cnt[idtfr]=1
    return cnt

train_cnt=build_cnt(sql_dataset["train"])
test_cnt=build_cnt(sql_dataset["test"])

def filter_rare_item_train(line):
    return train_cnt[line['idtfr']]>=5

def filter_rare_item_test(line):
    return test_cnt[line['idtfr']]>=5

sql_dataset["train"]=sql_dataset["train"].filter(filter_rare_item_train)
sql_dataset["test"]=sql_dataset["test"].filter(filter_rare_item_test)

print("after filter rare_item(<5)\n", len(sql_dataset["train"]), len(sql_dataset["test"]))

# build cluster range index
def build_cluster_range_index(dataset):
    idtfr_rng={}
    for i, line in enumerate(dataset):
        idtfr=line['idtfr']
        if line['idtfr'] not in idtfr_rng:
            idtfr_rng[idtfr]=[i,i]
        else:
            idtfr_rng[idtfr][1]=i
    return idtfr_rng

train_idtfr_rng=build_cluster_range_index(sql_dataset["train"])
test_idtfr_rng=build_cluster_range_index(sql_dataset["test"])

# split predicate and re combine
def generate_prompts_for_dataset(dataset, rows, idtfr_rng):
    length=len(dataset)
    result=[]

    for idtfr, rng in idtfr_rng.items():
        predi_lis=[]
        st, end=rng
        for pos in range(st, end+1):
            exp=dataset[pos]["exp"]
            




    for i in range(rows):
        if i%1000==0: print(f"{i}/{rows}")

        rand_cluster_row=random.randint(0,length-1)
        idtfr=dataset[rand_cluster_row]['idtfr']
        rng=idtfr_rng[idtfr]

        random_entry_ids=[random.randint(rng[0],rng[1]) for _ in range(example_num_each_row)]
        examples=dataset.select(random_entry_ids)
        
        # print(examples)

        prpt=generate_prompt(examples)
        # print("### prpt\n", prpt)

        result.append({"text":prpt})

    return result



# exit()

def get_area_from_chn_s(ss):
    tag_lis=ss.split(',')
    tag_lis=[x for x in tag_lis if x]

    ans=''
    maxcnt=-1
    for tag in tag_lis:
        for st in range(len(tag)):
            for j in range(st+1,len(tag)+1):
                ns=tag[st:j]
                cnt=0
                for tag_i in tag_lis:
                    if ns in tag_i: cnt+=1
                score=(j-st)*(cnt)
                if score>maxcnt:
                    maxcnt=score
                    ans=ns
    print(tag_lis)
    print(ans)
    return ans

def get_future_event_knowledge(timestamp):
    def cal_date_dis(dt1, dt2):
        return (dt2[0]-dt1[0])*30+(dt2[1]-dt1[1])
    

    future_event=""
    jieqi="""
立春：2月4日
雨水：2月19日
惊蛰：3月6日
春分：3月21日
清明：4月5日
谷雨：4月20日
立夏：5月6日
小满：5月21日
芒种：6月6日
夏至：6月22日
小暑：7月8日
大暑：7月23日
立秋：8月8日
处暑：8月23日
白露：9月8日
秋分：9月23日
寒露：10月8日
霜降：10月23日
立冬：11月7日
小雪：11月22日
大雪：12月7日
冬至：12月22日
小寒：1月6日
大寒：1月20日
"""
    jieqi_lis=jieqi.split('\n')
    jieqi_lis=[x.split('：') for x in jieqi_lis if x]
    jieqi_dict={}
    for jieqi, date in jieqi_lis:
        # use re to extract date, for example 2月4日
        month, day=re.search(r'(\d+)月(\d+)日', date).groups()
        jieqi_dict[(int(month),int(day))]=jieqi


    activities={
'1.15':"""XXX年货节
请介绍XXX年货节？
XXX年货节是XXX网举办的一项促销活动，主要面向春节前后的消费者，旨在满足消费者在春节前购买年货的需求。
XXX年货节一般在春节前一个月左右开始，持续时间大约为一个月，为消费者提供更多优惠和便利，让他们可以轻松购买到所需的年货。
除了XXX网，其他电商平台也会举办类似的年货节活动，以满足消费者的需求。

XXX年货节什么货品卖的好？
XXX年货节卖的最好的货品一般包括：食品、礼品、服装、家居用品、电器、美妆护肤等。
食品是XXX年货节上最受欢迎的商品，包括零食、酒水、调味品、糕点等，都是消费者在春节期间必备的食品。
礼品也是XXX年货节上的一大热门，包括节日礼品、年货礼盒、新年装饰品等，都是消费者在春节期间送礼的首选。
服装也是XXX年货节上的一大热门，包括男女装、鞋子、配饰等，都是消费者在春节期间换新装的首选。
家居用品也是XXX年货节上的一大热门，包括床上用品、厨房用品、家居装饰品等，都是消费者在春节期间换新家的必备。
电器也是XXX年货节上的一大热门，包括电视、冰箱、洗衣机、空调等，都是消费者在春节期间更换新家电的首选。
美妆护肤也是XXX年货节上的一大热门，包括护肤品、彩妆、美发产品等，都是消费者在春节期间保养自己的必备。""",


'3.18':"""XXX节日大促
3.18XXX节日大促是中国最大的女性购物节，它是由XXX旗下的XXX网发起的，旨在为女性消费者提供更多的优惠和便利，以满足她们在购买服装、美妆、家居等商品时的需求。
3.18XXX节日大促已经成为中国女性消费者最喜爱的购物节之一，它不仅提供了更多的优惠和便利，还为女性消费者提供了一个良好的购物环境，让她们可以轻松购买到所需的商品。

3.18哪些货品卖的好？
3.18XXX节日大促卖的最好的货品一般包括：服装、美妆、家居用品等。
服装是3.18XXX节日大促上最受欢迎的商品，包括女装、内衣、鞋子、配饰等，都是消费者在购物节期间购买的首选。
美妆也是3.18XXX节日大促上的一大热门，包括护肤品、彩妆、美发产品等，都是消费者在购物节期间购买的美容产品。
家居用品也是3.18XXX节日大促上的一大热门，包括床上用品、厨房用品、家居装饰品等，都是消费者在购物节期间购买的家居用品。
此外，3.18XXX节日大促上还会有一些特色商品，例如女性健康用品、女性时尚饰品等，也是消费者在购物节期间购买的热门商品。""",

'6.18':"""年中大促
6.18年中大促是中国最大的年中购物节，由XXX旗下的XXX网发起，每年6月18日左右举行。6.18年中大促是中国消费者最受欢迎的购物节之一，它旨在为消费者提供更多的优惠和便利，以满足他们在购买服装、美妆、家居等商品时的需求。

6.18年中大促哪些卖的好？
6.18年中大促卖的最好的货品一般包括：服装、美妆、家居用品等。
服装是6.18年中大促上最受欢迎的商品，包括女装、内衣、鞋子、配饰等，都是消费者在购物节期间购买的首选。
美妆也是6.18年中大促上的一大热门，包括护肤品、彩妆、美发产品等，都是消费者在购物节期间购买的美容产品。
家居用品也是6.18年中大促上的一大热门，包括床上用品、厨房用品、家居装饰品等，都是消费者在购物节期间购买的家居用品。
此外，6.18年中大促上还会有一些特色商品，例如女性健康用品、女性时尚饰品等，也是消费者在购物节期间购买的热门商品。""",

'8.8':"""会员节大促
8.8会员节大促是中国最大的会员购物节，由XXX旗下的XXX网发起，每年8月8日左右举行。8.8会员节大促是中国消费者最受欢迎的购物节之一，它旨在为XXX网的会员提供更多的优惠和便利，以满足他们在购买服装、美妆、家居等商品时的需求。

8.8会员节大促卖的最好的货品一般包括：服装、美妆、家居用品等。
服装是8.8会员节大促上最受欢迎的商品，包括女装、内衣、鞋子、配饰等，都是消费者在购物节期间购买的首选。
美妆也是8.8会员节大促上的一大热门，包括护肤品、彩妆、美发产品等，都是消费者在购物节期间购买的美容产品。
家居用品也是8.8会员节大促上的一大热门，包括床上用品、厨房用品、家居装饰品等，都是消费者在购物节期间购买的家居用品。
此外，8.8会员节大促上还会有一些特色商品，例如女性健康用品、女性时尚饰品等，也是消费者在购物节期间购买的热门商品。""",

'11.11':"""购物狂欢大促
11.11购物狂欢大促是中国最大的购物节，由XXX旗下的XXX网发起，每年11月11日左右举行。11.11购物狂欢大促是中国消费者最受欢迎的购物节之一，它旨在为消费者提供更多的优惠和便利，以满足他们在购买服装、美妆、家居等商品时的需求。

11.11购物狂欢大促什么品类卖的好？
11.11购物狂欢大促卖的最好的品类一般包括：服装、美妆、家居用品等。
服装是11.11购物狂欢大促上最受欢迎的商品，包括女装、内衣、鞋子、配饰等，都是消费者在购物节期间购买的首选。
美妆也是11.11购物狂欢大促上的一大热门，包括护肤品、彩妆、美发产品等，都是消费者在购物节期间购买的美容产品。
家居用品也是11.11购物狂欢大促上的一大热门，包括床上用品、厨房用品、家居装饰品等，都是消费者在购物节期间购买的家居用品。
此外，11.11购物狂欢大促上还会有一些特色商品，例如女性健康用品、女性时尚饰品等，也是消费者在购物节期间购买的热门商品。"""
    }

    activities_dict={}
    for date, act in activities.items():
        # use re to extract date
        month, day=date.split('.')
        activities_dict[(int(month),int(day))]=act

    
    # convert timestamp to (month, day)
    month, day=time.localtime(timestamp).tm_mon, time.localtime(timestamp).tm_mday

    # find the nearest jieqi
    for dt, jieqi in jieqi_dict.items():
        dis=cal_date_dis((month,day), dt)
        if dis>=0 and dis<15:
            future_event+=f"Near {dt[0]}月{dt[1]}日, {jieqi}, "
            break

    # find the nearest activity
    for dt, act in activities_dict.items():
        dis=cal_date_dis((month,day), dt)
        if dis>=0 and dis<15:
            future_event+=f"Near {dt[0]}月{dt[1]}日, {act}"
            break

    return future_event
    
    


pattern_chn = re.compile(u'[\u4e00-\u9fa5|,]')
def generate_prompt(exp_list):
    exp_num=len(exp_list)

    exp_list=exp_list.sort("timestamp")

    # print('-'*50)
    # for line in exp_list:
    #     print(line['exp'])

    instruction=f"Below are {exp_num-1} SQL expressions and their corresponding timestamps. Predict the materialized views corresponding to the consequent timestamp."

    template="-- Timestamp:\n{timestamp}\n-- Expression:\n{exp}\n\n"
    result=[]
    for entry in exp_list:
        entry_str=template.format(timestamp=entry['timestamp'], exp=entry['exp'])
        result.append(entry_str)

    chn_s=''.join(pattern_chn.findall(exp_list[-1]['exp']))
    pure_chn=chn_s.replace(',','')
    if pure_chn:
        area=get_area_from_chn_s(chn_s)
        inst_area=f'The materialized views is related to {area}.'
        # print("area\n"+area)
    else:
        inst_area=''

    lst_ts=exp_list[-1]['timestamp']
    future_event=get_future_event_knowledge(lst_ts)

    inst_infer_steps="""
Step 1 - Understand User Intent:
(1) Explain SQL expressions into nature language descriptions.
(2) Deduce the underlying user intent.
Step 2 - Integrate Event Factor Knowledge:
(1) Incorporate event factor knowledge.
(2) Assess how could the event influence the context of the query.
Step 3 - Predict Future Materialized Views:
(1) Predict the evolved query considering the integrated event knowledge and the inferred user intent.
(2) Suggest potential materialized views future that could optimize the evolved query.
Step 4 - Output Materialized Views.
    """

    if inst_area:
        res=f"{instruction} {inst_area} {future_event} {inst_infer_steps}\n\n{''.join(result)}"
    else:
        res=f"{instruction} {future_event} {inst_infer_steps}\n\n{''.join(result)}"
    # print(res)

    return res
    
def generate_prompts_for_dataset(dataset, rows, idtfr_rng):
    length=len(dataset)
    result=[]
    for i in range(rows):
        if i%1000==0: print(f"{i}/{rows}")

        rand_cluster_row=random.randint(0,length-1)
        idtfr=dataset[rand_cluster_row]['idtfr']
        rng=idtfr_rng[idtfr]

        random_entry_ids=[random.randint(rng[0],rng[1]) for _ in range(example_num_each_row)]
        examples=dataset.select(random_entry_ids)
        
        # print(examples)

        prpt=generate_prompt(examples)
        # print("### prpt\n", prpt)

        result.append({"text":prpt})

    return result




import json

train_texts=generate_prompts_for_dataset(sql_dataset["train"], train_rows, train_idtfr_rng)
test_texts=generate_prompts_for_dataset(sql_dataset["test"], test_rows, test_idtfr_rng)

# exit()
# sql_dataset["test"].to_json("./data/mv-exp-test.jsonl")
# sql_dataset["test"].to_csv("./data/mv-exp-test.csv")

with open(dst_train_file, "w") as fp:
    for entry in train_texts:
        json.dump(entry, fp)
        fp.write('\n')

with open(dst_test_file, "w") as fp:
    for entry in test_texts:
        json.dump(entry, fp)
        fp.write('\n')
