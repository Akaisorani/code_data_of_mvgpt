python gen_table1.py
python gen_table_dim_value.py 
python gen_dim_json.py
python gen_train_dataset_equal.py
python gen_derived_metrcis.py
python gen_yoy_lrr.py

python merge_json.py
rm -rf ../../train_mdl/data.json
cp ./all.json  ../../train_mdl/data.json
#rm -rf ./all.json
#rm -rf ./json/*