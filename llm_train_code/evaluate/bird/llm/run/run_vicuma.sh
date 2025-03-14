eval_path='./data/dev_test.json'
eval_path='./data/dev_simple.json'
#eval_path='./data/dev.json'
dev_path='./output/'
db_root_path='./data/dev_databases/'
use_knowledge='True'
not_use_knowledge='False'
mode='dev' # choose dev or dev
cot='True'
no_cot='Fales'
model='vicuna-13b-1.1'

YOUR_API_KEY=''

engine1='code-davinci-002'
engine2='text-davinci-003'
engine3='gpt-3.5-turbo'

# data_output_path='./exp_result/gpt_output/'
# data_kg_output_path='./exp_result/gpt_output_kg/'

#data_output_path='./exp_result/turbo_output/'
data_output_path='./exp_result/turbo_output_simple/'
#data_kg_output_path='./exp_result/turbo_output_kg/'
data_kg_output_path='./exp_result/turbo_output_kg_simple/'


echo 'generate GPT3.5 batch with knowledge'
python3 -u ./src/vicuma_request.py --db_root_path ${db_root_path}  --mode ${mode} \
--engine ${engine3} --eval_path ${eval_path} --data_output_path ${data_kg_output_path} --use_knowledge ${use_knowledge} \
--chain_of_thought ${no_cot} --model ${model}

echo 'generate GPT3.5 batch without knowledge'
#python3 -u ./src/vicuma_request.py --db_root_path ${db_root_path} --mode ${mode} \
#--engine ${engine3} --eval_path ${eval_path} --data_output_path ${data_output_path} --use_knowledge ${not_use_knowledge} \
#--chain_of_thought ${no_cot} --model ${model}
