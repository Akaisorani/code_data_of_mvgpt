# 使用方法：
# 1、换表名元信息table_meta
# 2、换问题模版question_pattern
# 3、换sql模版sql_pattern
# 4、替换一些参数

import random
import string

table_meta = {"table_name": "XXX_XXX_dp_view_rpt_shop_behavior_di", "table_desc": "存储了用户在店铺维度下的行为数据",
              "column": [{"header_id": "${group_dim_en_name}", "header_name": "${group_dim_cn_name}", "header_type": "${random_type}","data_type": "dimension", "header_unit": ""},
                         {"header_id": "${shop_id_column}", "header_name": "${subject_name}", "header_type": "${random_type}","data_type": "dimension", "header_unit": ""},
                         {"header_id": "pv_cnt", "header_name": "浏览次数", "header_type": "bigint","data_type": "metric", "header_unit": ""},
                         {"header_id": "se_clk_cnt", "header_name": "搜索点击次数", "header_type": "bigint","data_type": "metric",
                          "header_unit": ""},
                         {"header_id": "clt_cnt", "header_name": "收藏次数", "header_type": "bigint",
                          "data_type": "metric", "header_unit": ""},
                         {"header_id": "cart_cnt", "header_name": "加购次数", "header_type": "bigint","data_type": "metric",
                          "header_unit": ""},
                         {"header_id": "trd_amt", "header_name": "购买总金额", "header_type": "bigint","data_type": "metric",
                          "header_unit": ""},
                         {"header_id": "trd_cnt", "header_name": "购买笔数", "header_type": "bigint",
                          "data_type": "metric", "header_unit": ""},
                         {"header_id": "trd_num", "header_name": "购买商品个数", "header_type": "bigint",
                          "data_type": "metric", "header_unit": ""},
                         {"header_id": "${ds}", "header_name": "日期", "header_type": "${random_type}", "data_type": "dimension", "format": "${date_format}",
                          "header_unit": ""}], "rows": [{}],
              "symn": [{"浏览次数": "浏览总次数"}, {"购买笔数": "购买次数"}, {"总成交uv": "成交uv"},
                       {"总成交金额": "成交金额"}, {"总成交笔数": "总成交数"}, {"总成交笔数": "成交数"},
                       {"总成交笔数": "总成交数"}, {"类目ID": "类目"}, {"类目ID": "类目id"}, {"类目名称": "类目名"}]}

out_json_str = '''{"id":"${prompt_id}","conversations":[{"from":"human","value":"${prompt_value}"},{"from":"gpt","value":"${prompt_sql}"}]}'''

value_pattern = "表名称: ${table_name} table columns: ${table_column}。 使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql.  问题如下：${question} "

table_desc = table_meta["table_desc"]

type_list = ["bigint", "date", "string"]
data_type_list = ["metric", "dimension"]
header_id_list = ["zuobiao", "huanjing", "duide", "haishen", "huozhe", "huatong", "fengshan"]
header_name_list = ["坐标", "环境", "对得", "海参", "活着", "话筒", "风扇"]


cn_time_list = ["周", "月", "年"]
fun_time_list = ["WEEK", "MONTH", "YEAR"]
quention_list = ["有多少个", "有哪些", "是什么"]

random_type_list = ["string", "date", "int"]
date_pattern_list = ['toDate(${ds})', '${ds}', 'toDate(toString(${ds}))']


select_res_pattern_list = ['count(DISTINCT m_2.${group_dim_en_name}) AS count', '${group_dim_en_name}', '${group_dim_en_name}']
date_format_list = ['yyyyMMdd', 'yyyy-MM-dd', 'yyyy-MM-dd']

large_equal_list = [">=", ">", ">"]
large_equal_name_list = ["大于等于", "大于", "大于"]

small_equal_list = ["<=", "<", "<"]
small_equal_name_list = ["小于等于", "小于", "小于"]

predicate_list = ['', '为', '是']


def get_table_column(table_meta_info):
    column_list = table_meta_info["column"]
    for i  in range(1,4):
        idx = random.randint(0,6)
        column_list = column_list + [{"header_id": header_id_list[idx], "header_name": header_name_list[idx], "header_type": type_list[random.randint(0,2)], "data_type": data_type_list[random.randint(0,1)], "header_unit": ""}]

    column_list = random.sample(column_list, len(column_list))
    column_str = ""
    for i, column in enumerate(column_list):
        if i > 0:
            column_str += ","
        column_str += "%s [%s] (%s)" % (column["header_id"], column["header_type"], column["header_name"])
    return column_str

def generate_random_string(length):
    chars = string.ascii_letters
    return ''.join(random.choice(chars) for _ in range(length))

columns = table_meta["column"]
metric_column_list = [column for column in columns if "data_type" in column and column["data_type"] == 'metric']
symns = table_meta["symn"]

# sql_pattern_1 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND toDate(${ds}) >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 > ${min_value} AND m_2.sum1 < ${max_value};"
# question_pattern_1 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}大于${min_value}且小于${max_value}之间的人数是多少？"
#
# sql_pattern_2 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND toDate(${ds}) >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 > ${min_value} ;"
# question_pattern_2 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}大于${min_value}的人数是多少？"
#
# sql_pattern_3 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND toDate(${ds}) >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 < ${max_value} ;"
# question_pattern_3 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}小于${max_value}的人数是多少？"

# sql_pattern_1 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND ${ds} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 > ${min_value} AND m_2.sum1 < ${max_value};"
# question_pattern_1 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}大于${min_value}且小于${max_value}之间的人数是多少？"
#
# sql_pattern_2 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND ${ds} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 > ${min_value} ;"
# question_pattern_2 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}大于${min_value}的人数是多少？"
#
# sql_pattern_3 = "SELECT count(DISTINCT m_2.__aid) AS count from (SELECT SUM(${metric_name}) AS sum1, __aid AS __aid FROM ${table_name} WHERE ${shop_id_name} = ${shop_id}  AND ${ds} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY __aid) AS m_2 WHERE m_2.sum1 < ${max_value} ;"
# question_pattern_3 = "${subject}${shop_id}最近${day}${time_unit}${metricCnName}小于${max_value}的人数是多少？"


sql_pattern_1 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE m.sum ${large_equal} ${min_value} AND m.sum ${small_equal} ${max_value};"
question_pattern_1 = "${subject}${predicate}${shop_id}最近${day}${time_unit}${metricCnName}${large_equal_ch}${min_value}且${small_equal_ch}${max_value}的${group_dim_cn_name}${quention_name}？"

sql_pattern_2 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE m.sum ${large_equal} ${min_value} ;"
question_pattern_2 = "${subject}${predicate}${shop_id}最近${day}${time_unit}${metricCnName}${large_equal_ch}${min_value}的${group_dim_cn_name}${quention_name}？"

sql_pattern_3 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE  m.sum ${small_equal} ${max_value};"
question_pattern_3 = "${subject}${predicate}${shop_id}最近${day}${time_unit}${metricCnName}${small_equal_ch}${max_value}的${group_dim_cn_name}${quention_name}？"

sql_pattern_4 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE m.sum ${large_equal} ${min_value} AND m.sum ${small_equal} ${max_value};"
question_pattern_4 = "${shop_id}${predicate}${subject}最近${day}${time_unit}${metricCnName}${large_equal_ch}${min_value}且${small_equal_ch}${max_value}的${group_dim_cn_name}${quention_name}？"

sql_pattern_5 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE m.sum ${large_equal} ${min_value} ;"
question_pattern_5 = "${shop_id}${predicate}${subject}最近${day}${time_unit}${metricCnName}${large_equal_ch}${min_value}的${group_dim_cn_name}${quention_name}？"

sql_pattern_6 = "SELECT ${select_res_pattern} from (SELECT SUM(${metric_name}) AS sum, ${group_dim_en_name} AS ${group_dim_en_name} FROM ${table_name} WHERE ${shop_id_name} = ${shop_id} AND ${data_pattern} >= date_sub(${fun_time_unit}, ${day}, today()) GROUP BY ${group_dim_en_name}) AS m WHERE  m.sum ${small_equal} ${max_value};"
question_pattern_6 = "${shop_id}${predicate}${subject}最近${day}${time_unit}${metricCnName}${small_equal_ch}${max_value}的${group_dim_cn_name}${quention_name}？"


sql_pattern_list = [sql_pattern_1, sql_pattern_2, sql_pattern_3, sql_pattern_4, sql_pattern_5, sql_pattern_6]
question_pattern_list = [question_pattern_1, question_pattern_2, question_pattern_3, question_pattern_4, question_pattern_5, question_pattern_6]

result_list = []
for i in range(0, 5):
    question_pattern = question_pattern_list[i]
    sql_pattern = sql_pattern_list[i]
    for metric in metric_column_list:
        for day in range(1, 40):
            seed = random.randint(0, 2)
            length_random = random.randint(0, 15)
            ds_column = generate_random_string(length_random)
            cn_time_unit = cn_time_list[seed]
            func_time_unit = fun_time_list[seed]
            table_name = abs(table_meta["table_name"].__hash__()) - random.randint(1, 100000000)
            subject_name = generate_random_string(length_random)
            shop_id_name = generate_random_string(length_random)
            group_dim_cn_name = generate_random_string(length_random)
            group_dim_en_name = generate_random_string(length_random)
            quention_name = quention_list[seed]
            random_type = random_type_list[seed]
            select_res_pattern = select_res_pattern_list[seed]
            data_pattern = date_pattern_list[seed]
            date_format = date_format_list[seed]
            large_equal = large_equal_list[seed]
            large_equal_name = large_equal_name_list[seed]
            small_equal = small_equal_list[seed]
            small_equal_name = small_equal_name_list[seed]
            predicate = predicate_list[seed]

            table_column = get_table_column(table_meta).replace("${ds}", str(ds_column)).replace("${shop_id_column}", shop_id_name) \
                .replace("${subject_name}", subject_name).replace("${group_dim_cn_name}", group_dim_cn_name).replace("${group_dim_en_name}", group_dim_en_name) \
                .replace("${quention_name}", quention_name).replace("${random_type}", random_type)
            prompt_question = value_pattern.replace("${table_name}", str(table_name)).replace("${table_desc}", table_desc).replace("${table_column}", table_column).replace("${date_format}", date_format)

            metric_cn_name = metric["header_name"]
            metric_name = metric["header_id"]

            shop_id_list = [random.randint(1, 999999999), generate_random_string(length_random)]
            shop_id = shop_id_list[int(seed / 2)]

            cate_id = 2033221 + random.randint(1000, 2000)
            min_value = str(random.randint(1, 2000))
            max_value = str(random.randint(101, 99999))
            ##metric和day替换
            replace_question = question_pattern.replace("${day}", str(day)).replace("${metricCnName}",
                                                                                    metric_cn_name).replace(
                "${shop_id}", str(shop_id)).replace("${类目ID}", str(cate_id)).replace("${min_value}", min_value).replace(
                "${max_value}", max_value).replace("${time_unit}", cn_time_unit).replace("${ds}", str(ds_column)).replace("${subject}", subject_name) \
                .replace("${group_dim_cn_name}", group_dim_cn_name).replace("${quention_name}", quention_name).replace("${random_type}", random_type).replace("${large_equal_ch}", large_equal_name).replace("${small_equal_ch}", small_equal_name).replace("${predicate}", predicate)

            prompt_sql = sql_pattern.replace("${metric_name}", metric_name).replace("${day}", str(day)).replace("${select_res_pattern}", select_res_pattern).replace("${data_pattern}", data_pattern) \
                .replace("${shop_id}", str(shop_id)).replace("${cate_id}", str(cate_id)).replace("${min_value}", min_value).replace(
                "${max_value}", max_value).replace("week_num", str(day)).replace("${table_name}", str(table_name)) \
                .replace("${fun_time_unit}", func_time_unit).replace("${ds}", str(ds_column)).replace("${shop_id_name}",shop_id_name) \
                .replace("${group_dim_en_name}", group_dim_en_name).replace("${large_equal}", large_equal).replace("${small_equal}", small_equal)

            prompt_question_res = prompt_question.replace("${question}", replace_question)
            new_out_json = out_json_str.replace("${prompt_value}", prompt_question_res).replace("${prompt_sql}", prompt_sql).replace("${prompt_id}", str(i))
            i = i + 1
            #print(new_out_json)
            result_list.append(new_out_json)

            # 同义词替换S
            # for d in symns:
            #     for key, value in d.items():
            #         if key == metric_cn_name:
            #             new_metric_cn_name = value
            #             replace_question = question_pattern.replace("${day}", str(day)).replace("${metricCnName}",
            #                                                                             new_metric_cn_name).replace(
            #         "${shop_id}", str(shop_id)).replace("${类目ID}", str(cate_id)).replace("${min_value}", min_value).replace(
            #         "${max_value}", max_value)
            #             prompt_question_res = prompt_question.replace("${question}", replace_question)
            #             new_out_json = out_json_str.replace("${prompt_value}", prompt_question_res).replace("${prompt_sql}", prompt_sql).replace("${prompt_id}", str(i))
            #             i = i + 1
            #             print(new_out_json)
            #             result_list.append(new_out_json)



with open("json/train_dataset_equal.json", "w", encoding="utf-8") as f:
    f.write("[" + ','.join(result_list) + "]")
