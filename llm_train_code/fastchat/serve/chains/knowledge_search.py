# import sentence_transformers
import json

from langchain.embeddings import HuggingFaceEmbeddings
import numpy as np
import math
from fastchat.serve.dolphin import execute_dolphin_model_sql, execute_dolphin_sql
import requests
embeddings = HuggingFaceEmbeddings(model_name='./huggingface/text2vec-large-chinese')
# embeddings.client = sentence_transformers.SentenceTransformer(embeddings.model_name, device='cuda')

def get_prompt_embedding(prompt):
    query_embedding = embeddings.embed_query(prompt)
    a = np.array(query_embedding)
    a_l2 = a / np.linalg.norm(a, ord=2)
    return a_l2

def get_prompt_dim_info_topk(prompt, table, k):
    query_embedding = embeddings.embed_query(prompt)
    a = np.array(query_embedding)
    a_l2 = a / np.linalg.norm(a, ord=2)

    model_sql = """
    SELECT  id
            ,pm_approx_euclidean_distance(
                embedding
                ,CAST(
                    ARRAY[{}] AS float4[]
                )
            ) AS distance
    FROM vector_recall_dolphin.{}
    where cate_id in (1,2)
    ORDER BY distance ASC
    LIMIT {};""".format(','.join(map(str, a_l2)), table, k)
    id_list = execute_dolphin_model_sql(model_sql)
    new_id_list = [str(x[0]) for x in id_list]
    distance_list = [float(x[1]) for x in id_list]
    print(distance_list)
    #判断相关性
    top1, other = distance_list[0], distance_list[1:]
    similarity = [top1 * other_score / (math.sqrt(top1) * math.sqrt(other_score)) for other_score in other]
    print(similarity)
    threshold = 0.8
    if all([s < threshold for s in similarity]):
        print("召回的top1是最相关的答案")
    else:
        print("召回的top1存在歧义")

    select_sql = """
    select id, dim_type, dim_value, data from
    new_XXX.{}
    where id in ({});
    """.format(table, str(",".join(new_id_list)))
    sql_result = execute_dolphin_sql(select_sql)
    my_dict = {str(x[0]): x for x in sql_result}  # 使用字典构建器将子列表转换为字典
    print(my_dict)
    return new_id_list, distance_list, my_dict

def get_prompt_dim_info(prompt, table):
    query_embedding = embeddings.embed_query(prompt)
    a = np.array(query_embedding)
    a_l2 = a / np.linalg.norm(a, ord=2)

    model_sql = """
    SELECT  id
            ,pm_approx_euclidean_distance(
                embedding
                ,CAST(
                    ARRAY[{}] AS float4[]
                )
            ) AS distance
    FROM vector_recall_dolphin.{}
    where cate_id in (1,2)
    ORDER BY distance ASC
    LIMIT 1;""".format(','.join(map(str, a_l2)), table)
    id_list = execute_dolphin_model_sql(model_sql)
    id = id_list[0][0]
    distance = id_list[0][1]

    select_sql = """
    select id, dim_type, dim_value, data from
    new_XXX.{}
    where id = '{}';
    """.format(table, str(id))
    sql_result = execute_dolphin_sql(select_sql)
    dim_type = sql_result[0][1]
    dim_value = sql_result[0][2]
    data = sql_result[0][3]
    return dim_type, dim_value, distance, data

def get_prompt_knowledge(prompt, table):
    query_embedding = embeddings.embed_query(prompt)
    model_sql = """/*direct_sql=true,biz_key=kgb_kr_emb*/
    SELECT  id
            ,pm_approx_euclidean_distance(
                embedding
                ,CAST(
                    ARRAY[{}] AS float4[]
                )
            ) AS distance
    FROM  vector_recall_dolphin.{}
    ORDER BY distance ASC
    LIMIT 1;""".format(','.join(map(str, query_embedding)), table)
    id_list = execute_dolphin_model_sql(model_sql)
    id = id_list[0][0]
    select_sql = """
    select id, data from
    new_XXX.{}
    where id = '{}';
    """.format(table, str(id))
    sql_result = execute_dolphin_sql(select_sql)
    data = sql_result[0][1]
    q_a = data.split('|')
    return q_a[0], q_a[1]

def get_prompt_knowledge_top_k(prompt, table, k):
    query_embedding = embeddings.embed_query(prompt)
    model_sql = """/*direct_sql=true,biz_key=kgb_kr_emb*/
    SELECT  id
            ,pm_approx_euclidean_distance(
                embedding
                ,CAST(
                    ARRAY[{}] AS float4[]
                )
            ) AS distance
    FROM  vector_recall_dolphin.{}
    ORDER BY distance ASC
    LIMIT {};""".format(','.join(map(str, query_embedding)), table, k)
    id_list = execute_dolphin_model_sql(model_sql)
    new_id_list = [str(x[0]) for x in id_list]
    select_sql = """
    select id, question, answer from
    new_XXX.{}
    where id in ({});
    """.format(table, str(",".join(new_id_list)))
    sql_result = execute_dolphin_sql(select_sql)
    my_dict = {str(x[0]): x for x in sql_result}  # 使用字典构建器将子列表转换为字典
    print(my_dict)
    return new_id_list, my_dict
    # return q_a[0], q_a[1]

brand_map_dict = {"欧莱雅品牌": "brand_id是20068,",
                  "雅诗兰黛品牌": "brand_id是20034,",
                  "耐克品牌": "brand_id是20578,",
                  "华为品牌": "brand_id是11813,",
                  "雅马哈品牌": "brand_id是27207,",
                    "欧莱雅": "brand_id是20068,",
                  "雅诗兰黛": "brand_id是20034,",
                  "耐克": "brand_id是20578,",
                  "华为": "brand_id是11813,",
                  "雅马哈": "brand_id是27207,",

                  }
xcat1_id_map_dict = {
    "手机行业": "xcat1_id是5116,",
    "汽车行业": "xcat1_id是1132,",
    "女装行业": "xcat1_id是1104,",
    "装修行业": "xcat1_id是3406,",
    "美妆行业": "xcat1_id是4106,",
    "手机": "xcat1_id是5116,",
    "汽车": "xcat1_id是1132,",
    "女装": "xcat1_id是1104,",
    "装修": "xcat1_id是3406,",
    "美妆": "xcat1_id是4106,",
}

def replace_dict_values(d, s):
    for key, value in d.items():
        s = s.replace(key, str(value))
    return s

def trans_prompt(prompt, model_name):
    if prompt.startswith('提案分析'):
        url = "http://ai-models-provider.XXX.com/v1/chat/completions"
        content = "A chat between a curious user and an artificial intelligence assistant. " + "The assistant gives detailed, and polite answers to the users questions." + "\n从下面问题中提取维度值,返回结果为json。问题如下: \n" + prompt
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": content}]
        }
        print(payload)
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        response_entity = json.loads(response.text)
        print(response_entity)
        response_content = response_entity['choices'][0]["message"]['content']
        my_dict = json.loads(response_content)
        dimention = my_dict['dim_value_list']
        print(dimention)
        dim_type, dim_value, distance, data = get_prompt_dim_info(dimention, "XXX_dim_cate_brand_embedding")
        print(dim_type, dim_value, distance)
        if dim_type == 'brand_id':
            type_name = "品牌ID"
        else:
            type_name = "行业ID"
        if '品牌' in prompt:
            prompt = replace_dict_values(brand_map_dict, prompt)
        if '行业' in prompt:
            prompt = replace_dict_values(xcat1_id_map_dict, prompt)
        prompt = prompt.replace('提案分析',
                                  '表名称:  bp_XXX_rpt_amp_sap_item_action_stat_1d \n 描述:商家数据 \ntable columns:  ,item_id[BIGINT](宝贝ID), thedate[Date](日期) ,price_level[BIGINT](价格带层级:1-5),price_range[STRING](价格带区间),cate_id[BIGINT](行业ID),cate_name[STRING](行业名称),cate_level1_id[BIGINT](一级类目ID),cate_level1_name[STRING](一级类目名称),cate_level2_id[BIGINT](二级类目ID),cate_level2_name[STRING](二级类目名称),brand_id[BIGINT](品牌id),brand_name[STRING](品牌名称),xcat1_id[BIGINT](XXX类目id),xcat1_name[STRING](XXX类目名称),cust_type[STRING](访客在店铺的潜新老状态),is_item_old[STRING](是否宝贝老客),is_shop_old[STRING](是否店铺老客),is_brand_old[STRING](是否品牌老客),is_cate_old[STRING](是否叶子类目老客),is_cate2_old[STRING](是否二级类目老客),is_cate1_old[STRING](是否一级类目老客),is_xcat1_old[STRING](是否XXX行业老客),reserve_price[DOUBLE](当前价格(元)),item_price[DOUBLE](商品价格),ipv_1d[BIGINT](ipv数),se_clk_cnt[BIGINT](自然搜索的点击次数),alipay_cnt[BIGINT](成交笔数),alipay_amt[DOUBLE](成交金额(元)),alipay_quantity[BIGINT](成交件数),cart_cnt[BIGINT](加购数),col_item_cnt[BIGINT](收藏商品数),col_shop_cnt[BIGINT](收藏店铺数),prepay_cnt[BIGINT](预售支付定金笔数),prepay_amt[DOUBLE](预售总成交金额(元)),prepay_deposit_amt[DOUBLE](预售支付定金金额(元）),prepay_quantity[BIGINT](预售成交件数),{}[BIGINT]({}:,{}-{})。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下：'
                                  .format(dim_type, type_name, dim_value, data))
    return prompt

if __name__ == '__main__':
    # q, a = get_prompt_knowledge("万相台打底创意会随主图的变化而变化吗?")
    # print("\n".join(q))

    # dim_type, dim_value, distance, data = get_prompt_dim_info(c"黛丝少女品牌", "XXX_dim_cate_brand_embedding")
    # print(dim_type)
    # print(dim_value)
    # print(distance)
    # print(data)
    # dim_type, dim_value, distance, data = get_prompt_dim_info("Adidas/阿迪达斯品牌在过去一年的成交量有多少", "XXX_dim_cate_brand_embedding")
    # print(dim_type)
    # print(dim_value)
    # print(distance)
    # print(data)
    #
    # dim_type, dim_value, distance, data = get_prompt_dim_info("女装行业", "XXX_dim_cate_brand_embedding")
    # print(dim_type)
    # print(dim_value)
    # print(distance)
    # print(data)
    #
    # get_prompt_knowledge_top_k("你好", 'XXX_kgb_cmop_p4p_cmop_n_nopass_knowledges_embedding_knlg_data', 5)
    # dim_type, dim_value, distance, data = get_prompt_dim_info("阿迪达斯", "XXX_dim_cate_brand_embedding")
    # print(dim_type)
    # print(dim_value)
    # print(distance)
    # print(data)
    get_prompt_dim_info_topk("阿迪达斯", 'XXX_dim_cate_brand_embedding', 5)