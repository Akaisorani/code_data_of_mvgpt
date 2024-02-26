import csv
import os
import numpy as np
import pandas as pd
import random
from datasets import load_dataset
import re
import time
import json
import copy
import datetime
from expression import Predicate, Junction, Expression

import scipy as sp
from scipy.sparse import coo_matrix

import pgmpy
from pgmpy.models import BayesianModel, BayesianNetwork
from pgmpy.estimators import BayesianEstimator
from pgmpy.estimators import PC
from pgmpy.estimators import TreeSearch
from pgmpy.factors.discrete import TabularCPD
# from pgmpy.estimators.CITests import chi_square

src_dir="./results/240223"
src_dataset_file=os.path.join(src_dir,"exp_dataset.jsonl")
src_var_file=os.path.join(src_dir,"variables.csv")
temp_result_root="./results/240223"
temp_output_high_freq_file=os.path.join(temp_result_root,"output_mvs.txt")
num_proc=64
pd.set_option('display.max_colwidth', None)
TRAINING=True
load_exp_nrows=2000
USE_EXP_SEED=False
TOP_K_VARIABLES=5000
num_tuples_to_generate = 10000
DEBUG=True    # less data and variables number for faster training
DEBUG=False
if DEBUG:
    load_exp_nrows=1000
    TOP_K_VARIABLES=50
    num_tuples_to_generate = 10
bn_train_data_file=os.path.join(temp_result_root,"bn_train_data.npz")

bn_model_file = os.path.join(temp_result_root,'bn_model.bif')
bn_generated_mv_file = os.path.join(temp_result_root,'bn_generated_mvs.csv')
exp_seed_file=os.path.join(temp_result_root,'exp_seed.csv')

# mkdir etc
if not os.path.exists(temp_result_root):
    os.makedirs(temp_result_root)

def load_data(src_dataset_file, src_var_file, load_exp_nrows=load_exp_nrows, TOP_K_VARIABLES=TOP_K_VARIABLES):
    df_exp=pd.read_json(src_dataset_file, orient='records', lines=True, nrows=load_exp_nrows)
    print('columns:', df_exp.columns)
    print("df_exp", df_exp, sep='\n')


    # load variables
    df_variables=pd.read_csv(src_var_file, nrows=TOP_K_VARIABLES)
    print("df_variables", df_variables, sep='\n')

    # build mv data pandas df_mv
    mv_data={
        'exp_id': [],
        'shop_category_id': [],
        'mv_exp': [],
        'mv_hit_rate': []
    }
    for index, row in df_exp.iterrows():
        exp_id=row['exp_id']
        shop_category_id=row['shop_category_id']
        mv_exp_lis=row['mvs']
        mv_hit_num_per_day_lis=row['mv_hit_num_per_day']

        # add exp
        mv_data['exp_id'].append(exp_id)
        mv_data['shop_category_id'].append(shop_category_id)
        mv_data['mv_exp'].append(row['exp'])
        mv_data['mv_hit_rate'].append(min(mv_hit_num_per_day_lis))  # 用min值来近似exp的hit rate

        # add mvs
        for mv_exp, mv_hit_num_per_day in zip(mv_exp_lis, mv_hit_num_per_day_lis):
            mv_data['exp_id'].append(exp_id)
            mv_data['shop_category_id'].append(shop_category_id)
            mv_data['mv_exp'].append(mv_exp)
            mv_data['mv_hit_rate'].append(mv_hit_num_per_day)

    df_mv=pd.DataFrame(data=mv_data)
    print("load df_mv", df_mv, sep='\n')

    # df_mv.sort_values(by=['mv_hit_rate'], ascending=False, inplace=True)  # 不按hit rate排序，以保留时间序最早出现
    # print(df_mv)
    df_mv.drop_duplicates(subset='mv_exp', keep="first", inplace=True)
    # df_mv rename index to mv_id
    df_mv.reset_index(inplace=True, drop=True)
    df_mv['mv_id']=df_mv.index
    print("duplicate df_mv", df_mv, sep='\n')

    return df_exp, df_mv, df_variables

def parse_exp(df_mv):
    df_mv['exp_obj']=df_mv[['mv_exp','mv_id']].apply(lambda row: Expression.from_str(row['mv_exp'], _id=row['mv_id']), axis=1)

class Tokenizer(object):
    def __init__(self, df_variables):
        self.df_variables=df_variables
        self.var_tuple_to_id=dict(zip(zip(df_variables['identifier'], df_variables['operator'], df_variables['single_value']), df_variables['variable_id']))
        
    def tokenize(self, exp):
        # iter predicates in junctions in exp
        result_tokens=[]
        for junction in exp.junctions:
            for predicate in junction.predicates:
                # tokenize predicate
                values=predicate.value if isinstance(predicate.value, (list, tuple)) else [predicate.value]
                for value in values:
                    result_tokens.append(self.var_tuple_to_id.get((predicate.identifier, predicate.operator, value), -1))
        result_tokens=sorted(list(set(result_tokens)))
        if -1 in result_tokens:
            result_tokens.remove(-1)
        return result_tokens

def tokenize_exps(df_mv, tokenizer):
    # tokenize exp_list
    df_mv['exp_token_ids']=df_mv['exp_obj'].apply(lambda exp: tokenizer.tokenize(exp))

def encode_multi_hot_vec(df_mv, df_variables):

    # contains columns: shop_category_id, mv_hit_rate, var0, var1, var2, ...
    train_data={
        'shop_category_id': pd.arrays.SparseArray(df_mv['shop_category_id'], fill_value=0),
        'mv_hit_rate': pd.arrays.SparseArray(df_mv['mv_hit_rate'], fill_value=0)
    }

    # transform exp_token_ids to multi-hot vector
    # 1. build variable_id to row_number list in df_mv
    variable_id2row_number_list=dict()
    for index, row in df_mv.iterrows():
        for var_id in row['exp_token_ids']:
            if var_id not in variable_id2row_number_list:
                variable_id2row_number_list[var_id]=[]
            variable_id2row_number_list[var_id].append(index)
    # for each variable_name, create a new column in train_data
    L=len(df_mv)
    for var_id, var_name in zip(df_variables['variable_id'], df_variables['variable_name']):
        arr=np.zeros(L, dtype=np.int8)
        arr[variable_id2row_number_list.get(var_id, [])]=1
        sparse_arr=pd.arrays.SparseArray(arr)
        train_data[var_name]=sparse_arr
        del arr


    return pd.DataFrame(data=train_data)

def decode_multi_hot_vec(df_generated_data, df_variables):
    all_var_names=df_variables['variable_name'].values.tolist()
    all_var_names=[x for x in all_var_names if x in df_generated_data.columns] # sometimes, not all variables are in df_generated_data
    # transform multi-hot vector to varaible names
    var_names=df_generated_data[all_var_names].apply(lambda row: list(row[row==1].index), axis=1)
    var_names.name='var_names'
    print("decode", var_names, sep='\n')
    df_genmv_varnames=pd.concat([df_generated_data[['shop_category_id', 'mv_hit_rate']], var_names], axis=1)

    return df_genmv_varnames

def varnames2exp(varnames, df_variables, exp_id=None):
    # transform varnames to exp
    id_opIN_single_value=dict()
    predicates=[]
    for varname in varnames:
        identifier, operator, single_value=df_variables[df_variables['variable_name']==varname][['identifier', 'operator', 'single_value']].values[0]
        if operator=='IN':
            if (identifier, operator) not in id_opIN_single_value:
                id_opIN_single_value[(identifier, operator)]=[]
            id_opIN_single_value[(identifier, operator)].append(single_value)
        else:
            predicates.append(Predicate(identifier, operator, single_value))
    
    for (identifier, operator), single_values in id_opIN_single_value.items():
        predicates.append(Predicate(identifier, operator, single_values))
    
    exp=Expression(junctions=[Junction(predicates=predicates)], _id =exp_id)
    print("EXP",exp)
    return exp

def df_genmv_varnames2df_genmv(df_genmv_varnames, df_variables):
    df_genmv=df_genmv_varnames.copy()
    df_genmv['exp']=df_genmv_varnames.apply(lambda row: str(varnames2exp(row['var_names'], df_variables, row.index)), axis=1)
    # remove column shop_category_id, mv_hit_rate, var_names
    df_genmv.drop(columns=['shop_category_id', 'var_names'], inplace=True)
    # filter out empty exp
    df_genmv=df_genmv[df_genmv['exp']!='']
    return df_genmv

def save_sparse_dataframe(df, filename):
    # convert to scipy sparse matrix
    # spmatrix=coo_matrix(df.values)
    spmatrix=df.sparse.to_coo()
    # save to file
    sp.sparse.save_npz(filename, spmatrix)


def load_sparse_dataframe(filename):
    # load from file
    spmatrix=sp.sparse.load_npz(filename)
    # convert to pandas dataframe
    df=pd.DataFrame.sparse.from_spmatrix(spmatrix)
    return df


def PC_algo(df_train_data):
    est = PC(df_train_data)
    model=est.estimate(variant="stable", max_cond_vars=1)
    print(model.edges())

    return model

def ChowLiu_algo(df_train_data):
    est = TreeSearch(df_train_data, root_node="mv_hit_rate")
    dag = est.estimate(estimator_type="chow-liu")
    print(dag.nodes())
    print(dag.edges())
    model = BayesianNetwork(dag.edges())
    model.fit(
        df_train_data, estimator=BayesianEstimator, prior_type="dirichlet", pseudo_counts=0.1
    )
    print(model.get_cpds())

    return model

def data_describe(df_train_data):
    df_train_data=df_train_data.copy()
    # Discretizing mv_hit_rate
    df_train_data['mv_hit_rate'] = pd.cut(df_train_data['mv_hit_rate'], 10)

    model=ChowLiu_algo(df_train_data)

    return model

def load_model(model_file):
    bn_model = BayesianNetwork.load(model_file, filetype='bif')
    return bn_model

def save_model(bn_model, model_file):
    bn_model.save(model_file, filetype='bif')


def data_generate(model, virtual_evidence=[], n_samples=num_tuples_to_generate):
    virtual_evidence=virtual_evidence
    df_generated=model.simulate(n_samples=n_samples, virtual_evidence=virtual_evidence)

    return df_generated

def load_exp_as_soft_evidence(exp_seed_file, tokenizer, df_variables):
    df_exp_seed=pd.read_csv(exp_seed_file)
    exp_seed=df_exp_seed['exp'].values.tolist()[0]
    print("load seed", exp_seed, sep="\n")
    exp_seed_obj=Expression.from_str(exp_seed)
    exp_token_ids=tokenizer.tokenize(exp_seed_obj)
    exp_token_ids=[x for x in exp_token_ids if x in df_variables['variable_id'].values]
    var_names=[]
    for token_id in exp_token_ids:
        var_name=df_variables[df_variables['variable_id']==token_id]['variable_name'].values[0]
        var_names.append(var_name)
    print("parse var_names", var_names, sep="\n")
    # convert var_names to CPD tables
    virt_evidence=[]
    for var_name in var_names:
        cpd_table=TabularCPD(var_name, 2, [[0.2], [0.8]], state_names={var_name: [0, 1]})
        virt_evidence.append(cpd_table)
    print("virt_evidence", virt_evidence, sep="\n")

    return virt_evidence
    


if __name__=="__main__":
    df_exp, df_mv, df_variables = load_data(src_dataset_file, src_var_file, load_exp_nrows, TOP_K_VARIABLES)
    tokenizer=Tokenizer(df_variables)
    if TRAINING:
        parse_exp(df_mv)
        print(df_mv)
        
        tokenize_exps(df_mv, tokenizer)
        print(df_mv)
        print(df_mv.columns)
        df_train_data=encode_multi_hot_vec(df_mv, df_variables)  # df_train_data is sparse dataframe
        print("df_train_data", df_train_data, sep='\n')
        save_sparse_dataframe(df_train_data, bn_train_data_file)
        bn_model=data_describe(df_train_data)
        save_model(bn_model, bn_model_file)
    else:
        bn_model=load_model(bn_model_file)

    virtual_evidence=[]
    if USE_EXP_SEED:
        virtual_evidence=load_exp_as_soft_evidence(exp_seed_file, tokenizer, df_variables)

    df_generated_data=data_generate(bn_model, virtual_evidence=virtual_evidence, n_samples=num_tuples_to_generate)
    print("df_generated", df_generated_data, sep='\n')
    df_genmv_varnames=decode_multi_hot_vec(df_generated_data, df_variables)
    print(df_genmv_varnames)
    df_genmv=df_genmv_varnames2df_genmv(df_genmv_varnames, df_variables)
    print(df_genmv)
    df_genmv.to_csv(bn_generated_mv_file, index=False)



