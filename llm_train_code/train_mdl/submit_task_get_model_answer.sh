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
  model_name='analyticai-13b-mama_mvgen_v0712'
else
  model_name=$1
fi
if [ ! -n "$2" ]; then
  model_id='mvgen_v1'
else
  model_id=$2
fi
if [ ! -n "$3" ]; then
  question_file='data_test.json'
else
  question_file=$3
fi
if [ ! -n "$4" ]; then
  answer_file='answer_test_mvgen_v0712_all_x2_test.jsonl'
else
  answer_file=$4
fi
if [ ! -n "$5" ]; then
  num_gpus=2
else
  num_gpus=$5
fi
if [ ! -n "$6" ]; then
  # queue_name='kgb_llm'
  # queue_name='XXX_dolphin_llm'
  queue_name='mdl_a100_test_na61'
else
  queue_name=$6
fi
if [ ! -n "$7" ]; then
  XXXctl_path='XXXctl'
else
  XXXctl_path=$7
fi

 args="-Dmodel_path=/data/oss_bucket_0/ai_service/models/$model_name \
 -Dmodel_id=$model_id  \
 -Dquestion_file=$question_file  \
 -Danswer_file=/data/oss_bucket_0/ai_service/evaluation/$answer_file  \
 -Dnum_gpus=$num_gpus"
#  -Dquestion_begin=0 \
#  -Dquestion_end=32"
echo "${args}"
echo "$XXXctl_path"
$XXXctl_path run mdl --queue=$queue_name \
                  --entry=get_model_answer.py \
                  --algo_name=pytorch1131 \
                  --worker_count=$num_gpus \
                  --user_params="$args" \
                  --file.cluster_file=./cluster.json \
                  --ignore=venv,.git \
                  --oss_access_id=$oss_access_id \
                  --oss_access_key=$oss_access_key \
                  --oss_bucket=faeet2 \
                  --oss_endpoint=oss-accelerate.XXXcs.com \
                  --job_name="evaluate_$model_name"