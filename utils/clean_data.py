# 本文件主要读取原始数据，进行清洗空行，按时间排序的处理
import re
import pandas as pd


# 参数
sample_step=100

datapath="data/mv-gen-data/air_mv_0601_1127_0.csv"
dst_path=f"data/mv_exp_ts_cleaned_0901_1127_0_1in{sample_step}.csv"
dst_meta_data_path=dst_path+"_meta_data.json"

# read file
df=pd.read_csv(datapath, sep='#', header=None)
df.columns=['timestamp', 'member_id', 'shop_category_id', 'shop_category', 'exp']

# 清晰数据
# 删除exp空行
df = df.dropna(axis=0, how='any')
# euclidean_distance 向量 这种也删除
df=df[df['exp'].str.contains('euclidean_distance')==False]
# crowd_materialize_view_for_dmp.crowd_id 这种也删除
# df=df[df['exp'].str.contains('crowd_materialize_view_for_dmp.crowd_id')==False]

# 按时间排序
df.sort_values(by='timestamp', inplace=True)
# rearrange the index of df
df.index=range(len(df))

print(df)


# sample 1/5 of the data
df=df.iloc[::sample_step, :]
# print(df)

# 保存数据
df.to_csv(dst_path, sep="#", index=False)

# 获取数据统计信息，数量，时间区间等，保存到{}_meta_data.json
import time
import json
st_ts=df['timestamp'].min()
ed_ts=df['timestamp'].max()
st_time_str=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st_ts))
ed_time_str=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ed_ts))
tot_num=len(df)
columns=list(df.columns)
meta_data={
    "start_time": st_time_str,
    "end_time": ed_time_str,
    "rows": tot_num,
    "columns": columns
}
with open(dst_meta_data_path, "w") as fp:
    json.dump(meta_data, fp, indent=4)

