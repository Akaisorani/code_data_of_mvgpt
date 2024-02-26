#!/bin/bash

# before execute this script, please set conf in train_oss.ini
#   oss_id=xxxx
#   oss_key=xxxxxx
cd train_mdl
oss_access_id=$(grep "^oss_id=" train_oss.ini | cut -d'=' -f2)
oss_access_key=$(grep "^oss_key=" train_oss.ini | cut -d'=' -f2)

echo $oss_access_id
echo $oss_access_key

if [ ! -n "$1" ]; then
  out_modle_name='analyticai-13b-mama_sql_trysubmitmdl2'
else
  out_modle_name=$1
fi
if [ ! -n "$2" ]; then
  data_path='data_train.json'
else
  data_path=$2
fi
if [ ! -n "$3" ]; then
  base_model='vicuna-13b-1.3'
else
  base_model=$3
fi
if [ ! -n "$4" ]; then
  queue_name='kgb_llm'
else
  queue_name=$4
fi
if [ ! -n "$5" ]; then
  XXXctl_path='XXXctl'
else
  XXXctl_path=$5
fi

 args="-Dmodel_name_or_path=/data/oss_bucket_0/ai_service/models/$base_model \
 -Ddata_path=$data_path  \
 -Dbf16=True  \
 -Doutput_dir=/data/oss_bucket_0/ai_service/models/$out_modle_name \
 -Dnum_train_epochs=3  \
 -Dper_device_train_batch_size=2  \
 -Dper_device_eval_batch_size=2  \
 -Dgradient_accumulation_steps=16 \
 -Devaluation_strategy='no'  \
 -Dsave_strategy='steps'  \
 -Dsave_steps=1200 \
 -Dsave_total_limit=10  \
 -Dlearning_rate=2e-5  \
 -Dweight_decay=0.  \
 -Dwarmup_ratio=0.03  \
 -Dlr_scheduler_type='cosine'  \
 -Dlogging_steps=1  \
 -Dfsdp='full_shard auto_wrap'  \
 -Dfsdp_transformer_layer_cls_to_wrap='LlamaDecoderLayer'  \
 -Dtf32=True  \
 -Dmodel_max_length=2048  \
 -Dgradient_checkpointing=True  \
 -Dlazy_preprocess=True"
echo "${args}"
echo "$XXXctl_path"
$XXXctl_path run mdl --queue=$queue_name \
                  --entry=train_vicuna.py \
                  --algo_name=pytorch1131 \
                  --worker_count=1 \
                  --user_params="$args" \
                  --file.cluster_file=./cluster.json \
                  --ignore=venv,.git \
                  --oss_access_id=$oss_access_id \
                  --oss_access_key=$oss_access_key \
                  --oss_bucket=faeet2 \
                  --oss_endpoint=oss-accelerate.XXXcs.com \
                  --job_name=$out_modle_name