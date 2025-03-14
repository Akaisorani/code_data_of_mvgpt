import csv
import os
import pandas as pd
import random
from datasets import load_dataset
import re
import time
import json
import matplotlib.pyplot as plt
import copy
import datetime
from expression import Predicate, Junction, Expression
from workload_simulate import MaterializedView_collection, Workload

src_file="./data/mv_exp_ts_cleaned_0901_1127_0_1in100.csv"
dst_file="./data/exps_featurized.csv"
temp_result_root="./results/240101"
temp_output_high_freq_file=os.path.join(temp_result_root,"output_high_freq_mvs.txt")
temp_output_high_freq_junction_str_file=os.path.join(temp_result_root,"output_high_freq_origin_junction_str_mvs.txt")
num_proc=64
# select_top_k=5000
DEBUG=True
DEBUG=False
WRITE_OUT=True

# mkdir etc
if not os.path.exists(temp_result_root):
    os.makedirs(temp_result_root)

# load dataset
# columns=['timestamp', 'member_id', 'shop_ategory_id', 'shop_ategory', 'exp']
exp_dataset=load_dataset("csv", data_files=src_file, sep="#", split="train")
print(exp_dataset)

# use 10000 entries for debug
if DEBUG:
    exp_dataset=exp_dataset.select(range(10000))
    print(exp_dataset)

# guideline for feature engineering
# 1. extract exp identifiers
# 2. extract predicates and ids in IN clause
# 3. exp to multi-hot vector, store in variable id list format

# edit format, some feature engeering
def edit_exp(line):
    # replace \t and &&
    exp=line['exp']
    exp=exp.replace('\t',' ').replace('&&', ' and ')

    # format timestamp to timestr
    timestamp=line['timestamp']
    timestr=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    hour=int(time.strftime("%H", time.localtime(timestamp)))
    if hour>=0 and hour<6:
        time_seg='0-6'
    elif hour>=6 and hour<12:
        time_seg='6-12'
    elif hour>=12 and hour<18:
        time_seg='12-18'
    elif hour>=18 and hour<24:
        time_seg='18-24'


    return {"exp": exp, "timestr": timestr, "timeseg": time_seg}
exp_dataset=exp_dataset.map(edit_exp, num_proc=num_proc)
print(exp_dataset[:3])


# extract exp identifiers pattern: new_XXX.balabala.balabala
pattern=re.compile(r'new_XXX\.[.|\w]+')
def extract_identifiers(exp):
    identifiers_lis=pattern.findall(exp)
    identifiers_lis=list(set(identifiers_lis))
    identifiers_lis.sort()
    return identifiers_lis

# map function add_identifiers_feature
def add_identifiers_feature(line):
    identifiers_lis=extract_identifiers(line['exp'])
    identifiers_s=" ".join(identifiers_lis)
    return {"identifiers": identifiers_s}

exp_dataset=exp_dataset.map(add_identifiers_feature, num_proc=num_proc)
print(exp_dataset[:3])


# 2. extract predicates and ids in IN clause
# group by table name
exp_dataset=exp_dataset.add_column('exp_id', list(range(len(exp_dataset))))
exp_list=[]
for line in exp_dataset:
    exp_list.append(Expression.from_str(line['exp'], _id=line['exp_id']))
print(exp_list[:3])
# origin_junction_strs contains predicates with or structure
# for exp in exp_list[:10]:
#     print(exp.origin_junction_strs)
# exit()

# count junction frequency and output high freq junctions
def output_high_freq_junctions():
    junction_freq_dict={}
    for exp in exp_list:
        for junction in exp.junctions:
            junction_freq_dict[junction]=junction_freq_dict.get(junction, 0)+1
    print(len(junction_freq_dict))

    # sort junction by frequency, merged to code bellow 
    # junction_freq_lis=list(junction_freq_dict.items())
    # junction_freq_lis.sort(key=lambda x: x[1], reverse=True)
    # for junction, freq in junction_freq_lis[:3]:
    #     print(junction, freq)

    # get high freq junctions batch by batch, update junction freq
    # code below will modify junction_freq_dict and exp list, use deepcopy
    result_junctions=[]
    tot_num=10000
    batch_size=1000
    pre_exp_list=exp_list
    temp_junction_freq_dict=copy.deepcopy(junction_freq_dict)
    for i in range(tot_num//batch_size):
        # sort junction by frequency
        junction_freq_lis=list(temp_junction_freq_dict.items())
        junction_freq_lis.sort(key=lambda x: x[1], reverse=True)
        choosed_junction_list=junction_freq_lis[:batch_size]
        if len(choosed_junction_list)==0:
            print("no junctions left, stop")
            break
        print("rest exp list size", len(pre_exp_list))
        print("rest temp_junction_freq_dict size", len(temp_junction_freq_dict))
        print("choosed junction list freq range", choosed_junction_list[0][1], choosed_junction_list[-1][1])
        result_junctions.extend(choosed_junction_list)
        # update junction freq
        choosed_junction_set=set([x[0] for x in choosed_junction_list])
        next_step_exp_list=[]
        for exp in pre_exp_list:
            hit_flag=False
            for junction in exp.junctions:
                if junction in choosed_junction_set:
                    hit_flag=True
                    break
            if not hit_flag:
                next_step_exp_list.append(exp)
            else:
                # update junction freq
                for junction in exp.junctions:
                    if junction in temp_junction_freq_dict:
                        temp_junction_freq_dict[junction]-=1
        pre_exp_list=next_step_exp_list
        for junction in choosed_junction_set:
            del temp_junction_freq_dict[junction]

    if DEBUG:
        # print top 10 junctions
        print("top 10 temp choosed junctions")
        print("result length", len(result_junctions))
        for junction, freq in result_junctions[:10]:
            print(junction, freq)
    else:
        # temp output high freq junctions
        if WRITE_OUT:
            with open(temp_output_high_freq_file, "w") as fp:
                for junction, freq in result_junctions:
                    fp.write(str(junction)+"\n")
        pass

# count origin_junction_strs frequency and output high freq junctions  
def output_high_freq_origin_junction_strs():
    junction_freq_dict={}
    for exp in exp_list:
        for junction in exp.origin_junction_strs:
            junction_freq_dict[junction]=junction_freq_dict.get(junction, 0)+1
    print(len(junction_freq_dict))

    # sort junction by frequency, merged to code bellow 
    # junction_freq_lis=list(junction_freq_dict.items())
    # junction_freq_lis.sort(key=lambda x: x[1], reverse=True)
    # for junction, freq in junction_freq_lis[:3]:
    #     print(junction, freq)

    # get high freq junctions batch by batch, update junction freq
    # code below will modify junction_freq_dict and exp list, use deepcopy
    result_junctions=[]
    tot_num=10000
    batch_size=1000
    pre_exp_list=exp_list
    temp_junction_freq_dict=copy.deepcopy(junction_freq_dict)
    for i in range(tot_num//batch_size):
        # sort junction by frequency
        junction_freq_lis=list(temp_junction_freq_dict.items())
        junction_freq_lis.sort(key=lambda x: x[1], reverse=True)
        choosed_junction_list=junction_freq_lis[:batch_size]
        if len(choosed_junction_list)==0:
            print("no junctions left, stop")
            break
        print("rest exp list size", len(pre_exp_list))
        print("rest temp_junction_freq_dict size", len(temp_junction_freq_dict))
        print("choosed junction list freq range", choosed_junction_list[0][1], choosed_junction_list[-1][1])
        result_junctions.extend(choosed_junction_list)
        # update junction freq
        choosed_junction_set=set([x[0] for x in choosed_junction_list])
        next_step_exp_list=[]
        for exp in pre_exp_list:
            hit_flag=False
            for junction in exp.origin_junction_strs:
                if junction in choosed_junction_set:
                    hit_flag=True
                    break
            if not hit_flag:
                next_step_exp_list.append(exp)
            else:
                # update junction freq
                for junction in exp.origin_junction_strs:
                    if junction in temp_junction_freq_dict:
                        temp_junction_freq_dict[junction]-=1
        pre_exp_list=next_step_exp_list
        for junction in choosed_junction_set:
            del temp_junction_freq_dict[junction]

    if DEBUG:
        # print top 10 junctions
        print("top 10 temp choosed junctions")
        print("result length", len(result_junctions))
        for junction, freq in result_junctions[:10]:
            print(junction, freq)
        # check whether junctions in result_junctions have or structure
        print("check whether junctions in result_junctions have 'or' structure")
        for junction, freq in result_junctions[:100]:
            if ' or ' in junction:
                print(junction, freq)
    else:
        # temp output high freq junctions
        if WRITE_OUT:
            with open(temp_output_high_freq_junction_str_file, "w") as fp:
                for junction, freq in result_junctions:
                    fp.write(str(junction)+"\n")
        pass

output_high_freq_junctions()
output_high_freq_origin_junction_strs()
# exit()

# 3. exp to multi-hot vector
# 3.1 count cardinality of each column
# column_value_dictionalry={} # column -> {value set}
# value_frequency={}
# use pd for analyze
exp_data={
    'exp_id': [],
    'junction_id': [],
    'identifier': [],
    'operator': [],
    'single_value': []
}
for exp in exp_list:
    for junction_id, junction in enumerate(exp.junctions):
        for predicate in junction.predicates:
            identifier=predicate.identifier
            values=predicate.value if isinstance(predicate.value, (list, tuple)) else [predicate.value]

            for value in values:
                # df_exp.append({'exp_id': exp._id, 'identifier': identifier, 'operator': predicate.operator, 'single_value': value}, ignore_index=True)
                exp_data['exp_id'].append(exp._id)
                exp_data['junction_id'].append(junction_id)
                exp_data['identifier'].append(identifier)
                exp_data['operator'].append(predicate.operator)
                exp_data['single_value'].append(value)

pd.set_option('display.max_colwidth', None)
df_exp=pd.DataFrame(data=exp_data)
print(df_exp)
del exp_data
  
# use df, df_column_value_cardinality: [identifier, col_val_card]
df_column_value_cardinality=df_exp.groupby('identifier').agg(col_val_card=('single_value', 'nunique'))
df_column_value_cardinality.sort_values(by='col_val_card', ascending=False, inplace=True)
print(df_column_value_cardinality)
total_catdinality=df_column_value_cardinality['col_val_card'].sum(axis=0)
print('# total cardinality of values:', total_catdinality)

print("# top 20 cardinality of columns:")
print(df_column_value_cardinality.iloc[:20])

# use df, df_value_frequency: [identifier, single_value, val_freq]
df_value_frequency=df_exp.groupby(['identifier', 'operator','single_value']).agg(val_freq=('single_value', 'count'))
df_value_frequency.sort_values(by='val_freq', ascending=False, inplace=True)
df_value_frequency.reset_index(inplace=True)
df_value_frequency['rank']=df_value_frequency.index
# see distribution of predicate value frequency
if False:
    print("# top 20 frequency of values:")
    print(df_value_frequency.iloc[:20])

    check_lis=[0, 100, 1000, 5000, 10000, 20000, 50000, 100000, 300000, 400000, 600000, 800000]
    check_lis=[x for x in check_lis if x<len(df_value_frequency)]
    print(df_value_frequency.iloc[check_lis])
    # plot
    df_value_frequency.plot(x='rank', y='val_freq', kind='line', title='predicate value frequency', xlabel='predicate value id', ylabel='number', xlim=(0, 1000), ylim=(0, df_value_frequency['val_freq'].max()))
    plt.savefig(os.path.join(temp_result_root,'predicate_value_hist.pdf'), format='pdf', bbox_inches='tight', dpi=1000)

# see how many exps are hited by top k frequent values, help decide how many variables do we need
if False:
    # build index (identifier, value) -> rank
    # value_rank={}
    # for index, row in df_value_frequency.iterrows():
    #     value_rank[(row['identifier'], row['single_value'])]=index

    # traverse exps again, see how many exps are hited by top k frequent values

    # 1. merge df_exp and df_value_frequency
    df_exp_val_freq_rank=df_exp.merge(df_value_frequency, how='left', on=['identifier', 'single_value'])
    print(df_exp_val_freq_rank)

    # 2. hit: min of max of junction predicate value rank
    # group by column junction_id and agg max column rank
    df_exp_junction_max_val_rank=df_exp_val_freq_rank.groupby(['exp_id', 'junction_id']).agg(max_rank=('rank', 'max'))
    # group by column exp_id and agg min column max_rank
    df_exp_min_junction_val_rank=df_exp_junction_max_val_rank.groupby('exp_id').agg(min_rank=('max_rank', 'min'))
    print(df_exp_min_junction_val_rank)

    # 3. get the map min_rank -> covered exps number, for draw line chart to figure out how many variables do we need
    df_min_rank_covered_exps=df_exp_min_junction_val_rank.sort_values(by='min_rank', ascending=True).reset_index()
    df_min_rank_covered_exps['covered_exps_num']=df_min_rank_covered_exps.index+1
    df_min_rank_covered_exps=df_min_rank_covered_exps.groupby('min_rank', as_index=False).agg(covered_exps_num=('covered_exps_num', 'max'))
    print(df_min_rank_covered_exps)
    df_min_rank_covered_exps.plot(x='min_rank', y='covered_exps_num', kind='line', title='used variable number -> hit able exps number', xlabel='variable number', ylabel='hit exps number')
    plt.savefig(os.path.join(temp_result_root,'min_rank--covered_exps_num.pdf'), format='pdf', bbox_inches='tight', dpi=1000)

# 3.2 convert exp to multi-hot vector
# collect variables
df_variables=df_value_frequency[['identifier', 'operator', 'single_value', 'rank']].copy()
df_variables['variable_name']=df_variables['identifier']+'.'+df_variables['operator']+'.'+df_variables['single_value']
df_variables.rename(columns={'rank': 'variable_id'}, inplace=True)
print(df_variables)
# dump variables to file
if WRITE_OUT:
    df_variables.to_csv(os.path.join(temp_result_root,'variables.csv'), index=False)
var_id_index=dict([((row['identifier'], row['operator'], row['single_value']), row['variable_id']) for index, row in df_variables.iterrows()])

# commented, we move variable tokenization to train_bn.py
# df_exp['variable_id']=df_exp.apply(lambda row: var_id_index.get((row['identifier'], row['operator'], row['single_value']),-1), axis=1)
# df_exp_var_ids=df_exp[df_exp['variable_id']>=0].groupby('exp_id').agg(var_ids=('variable_id', list))
# print(df_exp_var_ids)
# ser_var_ids=df_exp_var_ids['var_ids']

# # add var_ids to exp_dataset
# def add_var_ids(line):
#     var_ids=ser_var_ids.get(line['exp_id'], [])
#     var_ids=sorted(list(set(var_ids)))

#     return {"var_ids": var_ids}

# exp_dataset=exp_dataset.map(add_var_ids, num_proc=num_proc)
# print(exp_dataset)

# add mvs to exp_dataset
exp_index=dict([[exp._id, exp] for exp in exp_list])
def add_mvs(line):
    exp=exp_index[line['exp_id']]
    junctions_str=[str(junction) for junction in exp.junctions]

    return {"mvs": junctions_str}
exp_dataset=exp_dataset.map(add_mvs, num_proc=num_proc)
print(exp_dataset)

# add mvs hit_num to exp_dataset
# first split exp datasets into days and simulate workload
st_ts=min(exp_dataset['timestamp'])
ed_ts=max(exp_dataset['timestamp'])
st_time=datetime.datetime.fromtimestamp(st_ts)
ed_time=datetime.datetime.fromtimestamp(ed_ts)
# add st_time by 1 day
second_day_time=st_time+datetime.timedelta(days=1)
second_day_time=second_day_time.replace(hour=0, minute=0, second=0)
time_sep_lis=[st_time]
while second_day_time<ed_time:
    time_sep_lis.append(second_day_time)
    second_day_time+=datetime.timedelta(days=1)
# if DEBUG and len(time_sep_lis)==1:
#     time_sep_lis.append(datetime.datetime.fromtimestamp((st_ts+ed_ts)//2))
time_sep_lis.append(ed_time)
print(time_sep_lis)
time_interval_lis=[(time_sep_lis[i], time_sep_lis[i+1]) for i in range(len(time_sep_lis)-1)]

# check exp_dataset exp_ids same to exp_list exp_ids
# print([e._id for e in exp_list]==list(exp_dataset['exp_id']))

workload=Workload()
workload.add_queries(exp_list, timestamps=list(exp_dataset['timestamp']))
mvs_collect=MaterializedView_collection()
# exp_ts_id_lis=list(zip(exp_dataset['timestamp'],exp_dataset['exp_id']))
mvs_addded_lastday=[]
for day_st_time, day_ed_time in time_interval_lis:
    print(day_st_time, day_ed_time)
    day_st_ts, day_ed_ts=day_st_time.timestamp(), day_ed_time.timestamp()
    # first execute queries in this time interval
    # second add mvs in this time interval
    # execute queries
    result=workload.execute_queries(mvs_collect, start_timestamp=day_st_ts, end_timestamp=day_ed_ts)
    # print('exe_num', result['exe_num'], 'hit_num', result['hit_num'], 'hit_flag', result['hit_flag'])

    # filter timestamp
    exp_dataset_interval=exp_dataset.filter(lambda x: x['timestamp']>=day_st_ts and x['timestamp']<day_ed_ts)
    mvs_in_interval=set()
    for mvs in exp_dataset_interval['mvs']:
        mvs_in_interval.update(mvs)
    create_times=[day_ed_ts]*len(mvs_in_interval)
    mvs_addded_lastday=mvs_collect.add_mvs(list(mvs_in_interval), create_times)
# commented below because first day workload can not hit new mvs last day, junctions in fisrt day workload were already in mvs_collect
# # mvs last day not be used, so run them with first day workload
# print(mvs_addded_lastday)
# mvs_collect_last_day=MaterializedView_collection()
# create_times=[ed_ts]*len(mvs_addded_lastday)
# mvs_collect_last_day.add_mvs(mvs_addded_lastday, create_times)
# result=workload.execute_queries(mvs_collect_last_day, start_timestamp=time_interval_lis[0][0].timestamp(), end_timestamp=time_interval_lis[0][1].timestamp())
# print('exe_num', result['exe_num'], 'hit_num', result['hit_num'], 'hit_flag', result['hit_flag'])
# # merge mv_collect and mv_collect_last_day
# mvs_collect.add_mv_collection(mvs_collect_last_day)
hit_num_list=[mvs_collect.hit_num[x] for x in mvs_collect.mvs]
hit_num_per_day_list=[(hit_num/((ed_ts-create_time)/86400) if hit_num>0 else 0) for hit_num, create_time in zip(hit_num_list, mvs_collect.create_times)]
mv_hit_num_index=dict([(str(mvs), hit_num) for mvs, hit_num in zip(mvs_collect.mvs, hit_num_per_day_list)])
def add_mv_hit_num(line):
    mvs=line['mvs']
    hit_num_list=[mv_hit_num_index.get(mv, 0) for mv in mvs]
    return {"mv_hit_num_per_day": hit_num_list}
exp_dataset=exp_dataset.map(add_mv_hit_num, num_proc=num_proc)

if WRITE_OUT:
    exp_dataset.to_json(os.path.join(temp_result_root,'exp_dataset.jsonl'), force_ascii=False)
