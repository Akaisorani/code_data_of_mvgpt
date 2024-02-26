# Materialized View Generation

## Description
Using pre-trained natural language models and Bayesian networks, fine-tune the task of predicting materialized views. Input instructions and historical queries, output materialized view statements for future use.

## File structure
`llm_train_code/`: llama model training framework\
`utils/preprocess_csv_text.py`: build train and test file: mv-train and mv-test\
`utils/clean_data.py`: clean the data from original query log\
`bn_train_code/generate_features.py`: feature extraction\
`bn_train_code/train_bn.py`: training bayesian network