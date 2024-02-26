import json,random,string
from string import Template

from gen_table1 import getRandomTimeRange


#support yoy(), year on year and lrr() link relative ratio(环比) function. 

def getRandomStr(len):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=len))

def genPromptAndSql(data, prompt_template1, sql_template1):
    # prompt_template1='表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}是${rand_dim_val}${other_dim_list}, 本月每天的${metric_comment}是多少${order_prompt}.${limit_prompt}'
    # sql_template1="select thedate, ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and thedate >= toStartOfMonth(today()) group by thedate ${order}${limit}"
    
    table_name = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
    dim_list=[]
    metric_list = []
    thedate_item= []
    for item in data['column']:
        if item['header_id'] == 'thedate':
            thedate_item.append(item)
        elif item['header_id'] == 'f_impression' or item['header_id'] == 'ipv_1d' :
            metric_list.append(item)
        else:
            if len(metric_list) == 0:
                dim_list.append(item)
            else:
                metric_list.append(item)

    prompt_dim = random.sample(dim_list, 7)
    prompt_dim.append(thedate_item[0])

    #generate random field and dim value
    tmp_dim_field_len = random.randint(6, 10)
    dim_field1 = { 'header_id':getRandomStr(tmp_dim_field_len),
                   'header_type': random.sample(["BIGINT",'STRING'], 1)[0]
                   , "header_name": getRandomStr(tmp_dim_field_len)
                 }
    dim_field2 = { 'header_id':getRandomStr(tmp_dim_field_len),
                'header_type': random.sample(["BIGINT",'STRING'], 1)[0]
                , "header_name": getRandomStr(tmp_dim_field_len)
                }
    field1_options =[]
    field2_options =[]
    tmp_dim1_desc=""
    tmp_dim2_desc=""
    tmp_option_num = random.randint(3, 8)
    for i in range(0,tmp_option_num):
        item1_option={'option':getRandomStr(random.randint(6, 10)),'desc': getRandomStr(random.randint(6, 10))}
        item2_option={'option':getRandomStr(random.randint(6, 10)),'desc': getRandomStr(random.randint(6, 10))}
        field1_options.append(item1_option)
        field2_options.append(item2_option)
        tmp_dim1_desc += "," +item1_option['option']+"-"+item1_option['desc']
        tmp_dim2_desc += "," +item2_option['option']+"-"+item2_option['desc']
    
    dim_field1['header_name'] += ':'+ tmp_dim1_desc
    dim_field2['header_name'] += ':'+ tmp_dim2_desc

    prompt_dim.append(dim_field1)
    prompt_dim.append(dim_field2)
    


    prompt_dim = random.sample(prompt_dim, 10)
    prompt_metric = random.sample(metric_list, 10)

    col_fileds=""
    all_fields= prompt_dim + prompt_metric
    for item in all_fields:
        if len(col_fileds) > 1:
            col_fileds = col_fileds +","
        col_fileds = col_fileds + item['header_id'] + "[" + item['header_type']  +"](" +  item['header_name'] + ")"

    prompt_dim = random.sample(prompt_dim, 8)
    prompt_metric = random.sample(prompt_metric, 10)

    main_dim_comment = prompt_dim[0]['header_name'].split(":")[0]
    main_dim = prompt_dim[0]['header_id']
    rand_dim_val = str(random.randint(0, 100000))
    if '是否' in main_dim_comment:
        rand_dim_val = 1
        main_dim_comment = main_dim_comment.replace('是否','')
    if(prompt_dim[0]['header_type']) == 'STRING':
        rand_dim_val = "'" + str(rand_dim_val) +"'"
    if main_dim == 'thedate':
        main_dim = prompt_dim[5]['header_id']
        main_dim_comment = prompt_dim[5]['header_name'].split(":")[0]
    
    



    dim_list_cnt = random.randint(1, 2)
    other_dim_list=''
    other_dim_filter=''

    #add one dim
    tmp_value = str(random.randint(0, 100000))
    if '是否' in prompt_dim[4]['header_name']:
        tmp_value = 1
        one_dim_list = prompt_dim[4]['header_name'].split(":")[0].replace(".",'').replace('。', '').replace('是否', '')
    else:
        one_dim_list = prompt_dim[4]['header_name'].split(":")[0].replace(".",'').replace('。', '')+ "是" +str(tmp_value)
    one_dim_filter = prompt_dim[4]['header_id']+"="
    if prompt_dim[4]['header_type'] == 'STRING':
        one_dim_filter += "'" + str(tmp_value) +"'"
    else:
        one_dim_filter +=  str(tmp_value)


    other_dim_list = other_dim_list + ","
    other_dim_filter = other_dim_filter + " and "
    tmp_option_pos = random.randint(0,len(field1_options)-1)
    other_dim_list += field1_options[tmp_option_pos]['desc']
    other_dim_filter += dim_field1['header_id']+"="
    tmp_value = field1_options[tmp_option_pos]['option']
    if dim_field1['header_type'] == 'STRING':
        other_dim_filter += "'" + str(tmp_value) +"'"
    else:
        other_dim_filter +=  str(tmp_value)


    if dim_list_cnt > 1:
        other_dim_list = other_dim_list + ","
        other_dim_filter = other_dim_filter + " and "
        tmp_option_pos = random.randint(0,len(field2_options)-1)
        other_dim_list += field2_options[tmp_option_pos]['desc']
        other_dim_filter += dim_field2['header_id']+"="
        tmp_value = field2_options[tmp_option_pos]['option']
        if dim_field2['header_type'] == 'STRING':
            other_dim_filter += "'" + str(tmp_value) +"'"
        else:
            other_dim_filter +=  str(tmp_value)
            


    metric_comment=""
    metric_sum_func = ""
    one_metric_comment = ''
    one_metric_order_comment = ''
    one_metric_order = ''
    one_metric_sum_func = ''
    one_metric_col = ''
    dim_metric_cnt = random.randint(2, 3)
    for i in range(0,dim_metric_cnt):
        if(len(metric_comment) > 0):
            metric_comment += ","
            metric_sum_func += ","
        tmp_col_desc_len = len(prompt_metric[i]['header_name'].split(","))
        if tmp_col_desc_len > 1 :
            tmp_col_desc_pos = random.randint(0, tmp_col_desc_len-1)
            one_metric_comment = prompt_metric[i]['header_name'].split(",")[tmp_col_desc_pos]
        else:
            one_metric_comment = prompt_metric[i]['header_name']
        
        metric_field_tmp = prompt_metric[i]['header_id']
        lrr_option_select = random.randint(0, 3)
        if lrr_option_select ==0:
            metric_comment += one_metric_comment
            metric_sum_func += "sum("+metric_field_tmp+") as "+ metric_field_tmp
            one_metric_sum_func = "sum("+metric_field_tmp+") as "+ metric_field_tmp
            one_metric_col = metric_field_tmp
        elif lrr_option_select ==1:
            #yoy
            metric_comment += one_metric_comment+"同比"
            one_metric_sum_func = "lrr(sum("+metric_field_tmp+"), thedate, date_add(YEAR, -1, thedate)) as "+ metric_field_tmp+"_yoy"
            metric_sum_func += one_metric_sum_func
            one_metric_col = metric_field_tmp
        elif lrr_option_select == 2:
            #月环比
            month_tmp_str = ""
            if random.randint(0, 1) == 1:
                month_tmp_str = "月"
            metric_comment += one_metric_comment+month_tmp_str+"环比"
            one_metric_sum_func = "lrr(sum("+metric_field_tmp+"), thedate, date_add(MONTH, -1, thedate)) as "+ metric_field_tmp+"_lrr_m"
            metric_sum_func += one_metric_sum_func
            one_metric_col = metric_field_tmp
        elif lrr_option_select == 3:
            #月环比
            metric_comment += one_metric_comment+"周环比"
            one_metric_sum_func = "lrr(sum("+metric_field_tmp+"), thedate, date_add(WEEK, -1, thedate)) as "+ metric_field_tmp+"_lrr_w"
            metric_sum_func += one_metric_sum_func
            one_metric_col = metric_field_tmp


    metric_comment = metric_comment.replace('(元)','')
    one_metric_comment = one_metric_comment.replace('(元)','')




    
    
    order_select = random.randint(0, 2)
    order_prompt = random.sample(["升",'顺'], 1)[0]
    order = 'order by thedate asc'
    dim_order_prompt = random.sample(["升",'顺'], 1)[0]
    dim_order = 'order by '+ main_dim +' asc'
    if order_select == 1:
        order_prompt = random.sample(["降",'逆'], 1)[0]
        order = 'order by thedate desc'
        dim_order_prompt = random.sample(["降",'逆'], 1)[0]
        dim_order = 'order by '+ main_dim +' desc'
    elif order_select == 2:
        order_prompt=""
        order = ""
        dim_order_prompt = ''
        dim_order = ''
    
    if len(order_prompt) > 0:
        order_prompt = ",按时间的"+order_prompt+"序排列"
        dim_order_prompt = ",按"+main_dim_comment+"的"+dim_order_prompt+"序排列"
    
    limit_prompt = ""
    limit = ""
    limit_select = random.randint(0, 1)
    if limit_select == 1:
        limit_num = random.randint(1, 100)
        limit_prompt = random.sample(["显示",'展示','返回','保留'], 1)[0] + str(limit_num) + random.sample(["条",'行'], 1)[0]+ random.sample(["数据",'结果'], 1)[0]
        limit = " limit "+ str(limit_num)

    
    time_range_comment, time_range = getRandomTimeRange()
    equal_comment = random.sample(["是",'等于','为','',' '], 1)[0]
    time_range_comment = time_range_comment + random.sample(["的",'',','], 1)[0]



    #top N
    randK = random.randint(1, 10)
    rank_str = str(randK)
    if(randK == 1):
        rank_str = random.sample(['1',''], 1)[0]
    top_limit = 'limit '+ str(randK)
    tmp_top_select = random.randint(0, 1)
    if tmp_top_select == 1:
        #desc

        tmp_shift = random.randint(0, 1)
        if tmp_shift == 0:
            top_comment = one_metric_comment + random.sample(['top','top ','max',"最高","最大",'最大的','最高的','最多的'], 1)[0] + rank_str + random.sample(['位','个','',' '], 1)[0]
        else:
            top_comment = random.sample(['top','max',"最高","最大",'最大的','最高的','最多的'], 1)[0] + rank_str + random.sample(['位','个','的','',' '], 1)[0]+one_metric_comment
        top_order = ' order by '+one_metric_col+" desc "
    else:
        tmp_shift = random.randint(0, 1)
        if tmp_shift == 0:
            top_comment = one_metric_comment + random.sample(['min',"最低","最小","最小的","最少的",'minimized','lowest'], 1)[0] + rank_str + random.sample(['位','个','',' '], 1)[0]
        else:
            top_comment = random.sample(['min',"最低","最小","最小的","最少的",'minimized','lowest'], 1)[0] + rank_str + random.sample(['位','个','',' '], 1)[0]+one_metric_comment
        top_order = ' order by '+one_metric_col+" asc "

    top_question_mark= random.sample(['分别是谁',"是谁？","是哪些？",'分别是哪些？','有哪些','是哪几个?','是?','?',' ',''], 1)[0]


    #quarter_order_prompt,quarter_order, month_order_prompt,month_order,week_order_prompt,week_order
    if order_select == 1:
        quarter_order_prompt = ",按"+random.sample(['时间','日期',"季度"], 1)[0]+"的"+random.sample(["降",'逆'], 1)[0]+"序排列"
        quarter_order = ' order by toStartOfQuarter(thedate) desc '
        month_order_prompt = ",按"+random.sample(['时间','日期',"月"], 1)[0]+"的"+random.sample(["降",'逆'], 1)[0]+"序排列"
        month_order = ' order by toYYYYMM(thedate) desc '
        week_order_prompt = ",按"+random.sample(['时间','日期',"周"], 1)[0]+"的"+random.sample(["降",'逆'], 1)[0]+"序排列"
        week_order = ' order by toISOWeek(thedate) desc '
        year_order_prompt = ",按"+random.sample(['时间','日期',"年"], 1)[0]+"的"+random.sample(["降",'逆'], 1)[0]+"序排列"
        year_order = ' order by toYear(thedate) desc '
        one_metric_order_comment = ",按" + str(one_metric_comment) + "的"+random.sample(["降",'逆'], 1)[0]+"序排列"
        one_metric_order = ' order by ' + one_metric_col +' desc '
    elif order_select == 0:
        quarter_order_prompt = ",按"+random.sample(['时间','日期',"季度"], 1)[0]+"的"+random.sample(["升",'顺'], 1)[0]+"序排列"
        quarter_order = ' order by toStartOfQuarter(thedate) asc '
        month_order_prompt = ",按"+random.sample(['时间','日期',"月"], 1)[0]+"的"+random.sample(["升",'顺'], 1)[0]+"序排列"
        month_order = ' order by toYYYYMM(thedate) asc '
        week_order_prompt = ",按"+random.sample(['时间','日期',"周"], 1)[0]+"的"+random.sample(["升",'顺'], 1)[0]+"序排列"
        week_order = ' order by toISOWeek(thedate) asc '
        year_order_prompt = ",按"+random.sample(['时间','日期',"年"], 1)[0]+"的"+random.sample(["升",'顺'], 1)[0]+"序排列"
        year_order = ' order by toYear(thedate) asc '
        one_metric_order_comment = ",按" + str(one_metric_comment) + "的"+random.sample(["升",'顺'], 1)[0]+"序排列"
        one_metric_order = ' order by ' + one_metric_col +' asc '
    else:
        quarter_order_prompt = ''
        quarter_order = ''
        month_order_prompt = ''
        month_order = ''
        week_order_prompt = ''
        week_order = ''
        year_order_prompt = ''
        year_order = ''
        one_metric_order_comment = ''
        one_metric_order = ''

 

    template1 = Template(prompt_template1)
    prompt = template1.substitute(table_name=table_name, col_fileds=col_fileds, main_dim_comment=main_dim_comment
                                  , rand_dim_val=rand_dim_val,other_dim_list=other_dim_list,metric_comment=metric_comment
                                  ,order_prompt=order_prompt,dim_order_prompt=dim_order_prompt,limit_prompt=limit_prompt,time_range_comment=time_range_comment,equal_comment=equal_comment,one_dim_list=one_dim_list,top_comment=top_comment,top_question_mark=top_question_mark,quarter_order_prompt=quarter_order_prompt,month_order_prompt=month_order_prompt,week_order_prompt=week_order_prompt,year_order_prompt=year_order_prompt,one_metric_order_comment=one_metric_order_comment)
    template2 = Template(sql_template1)
    sql = template2.substitute(metric_sum_func=metric_sum_func,table_name=table_name,main_dim=main_dim,rand_dim_val=rand_dim_val
                               ,other_dim_filter=other_dim_filter,order=order,dim_order=dim_order,limit=limit,time_range=time_range,one_dim_filter=one_dim_filter,one_metric_sum_func=one_metric_sum_func, one_metric_col=one_metric_col,top_order=top_order,top_limit=top_limit,quarter_order=quarter_order,month_order=month_order,week_order=week_order,year_order=year_order,one_metric_order=one_metric_order)
    

    #change thedate
    thedate_new_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    prompt = prompt.replace('thedate',thedate_new_name)
    sql = sql.replace('thedate',thedate_new_name)

    thedate_comment = random.sample(["日期",'数据日期','时间','数据时间'], 1)[0]
    prompt = prompt.replace('日期',thedate_comment)

    question_mark = random.sample(["是多少 ","是多少?",'有多少?','','总量 ','总量?','总量有多少?','总和 ','总和?','总和有多少?','总和是多少?'], 1)[0]
    prompt = prompt.replace('是多少?',question_mark)
    prompt = prompt.replace("'",'')
    
    return (prompt,sql)


template_list = [{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}每天的${metric_comment}是多少?${order_prompt}.${limit_prompt}',
"sql_template":"select thedate, ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} group by thedate ${order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}每周${metric_comment}是多少?${week_order_prompt}.${limit_prompt}',
"sql_template":"select toISOWeek(thedate), ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} group by toISOWeek(thedate) ${week_order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}每月的${metric_comment}是多少?${month_order_prompt}.${limit_prompt}',
"sql_template":"select toYYYYMM(thedate), ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} group by toYYYYMM(thedate) ${month_order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}每季度的${metric_comment}是多少?${quarter_order_prompt}.${limit_prompt}',
"sql_template":"select toStartOfQuarter(thedate), ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} group by toStartOfQuarter(thedate) ${quarter_order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}每年${metric_comment}是多少?${year_order_prompt}.${limit_prompt}',
"sql_template":"select toYear(thedate), ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} group by toYear(thedate) ${year_order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${other_dim_list}, ${time_range_comment}的${metric_comment}是多少?按${main_dim_comment}分组 ${dim_order_prompt}.${limit_prompt}',
"sql_template":"select ${main_dim}, ${metric_sum_func} from ${table_name} where  ${time_range} ${other_dim_filter} group by ${main_dim} ${dim_order}${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${main_dim_comment}${equal_comment}${rand_dim_val}${other_dim_list}, ${time_range_comment}${metric_comment}是多少?${limit_prompt}',
"sql_template":"select ${metric_sum_func} from ${table_name} where  ${main_dim}=${rand_dim_val} ${other_dim_filter} and ${time_range} ${limit}"}

,{"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下： ${other_dim_list}, ${time_range_comment}每天的${metric_comment}是多少?按${main_dim_comment}分组${order_prompt}.${limit_prompt}',
"sql_template":"select thedate,${main_dim}, ${metric_sum_func} from ${table_name} where  ${time_range} ${other_dim_filter}   group by thedate,${main_dim} ${order}${limit}"}

, {"prompt_template":'表名称: ${table_name}\n table columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下：${other_dim_list}, ${time_range_comment}${top_comment}的${main_dim_comment}${top_question_mark}',
"sql_template":"select ${main_dim}, ${one_metric_sum_func} from ${table_name} where  ${time_range} ${other_dim_filter}  group by ${main_dim} ${top_order} ${top_limit}"}
]

# template_list = [
#   {"prompt_template":'表名称: ${table_name}\n 描述:商家数据 \ntable columns: ${col_fileds}。\n使用以上表来生成clickhouse sql来回答问题,返回格式为纯sql. 问题如下：  ${time_range_comment}${metric_comment}是多少? ${one_metric_order_comment}.${limit_prompt}',
# "sql_template":"select  ${metric_sum_func} from ${table_name} where ${time_range}  ${one_metric_order}${limit}"}
# ]

def genrate_corpus(rows, table_schema):
    #table_schema= '../table1.json'
    with open(table_schema, 'r') as f:
        table1 = json.load(f)

    all_conv = []
    for i in range(0, rows):
        conv = []
        idx = random.randint(0, len(template_list) - 1)
        prompt,sql = genPromptAndSql(table1,template_list[idx]['prompt_template'], template_list[idx]['sql_template'])
        q={}
        q['from']='human'
        q['value']=prompt

        a={}
        a['from']='gpt'
        a['value']=sql
        conv.append(q)
        conv.append(a)

        one_item={"id":i, "conversations":conv}
        all_conv.append(one_item)


    with open("json/corpus_yoy_lrr.json", "w") as f:
        json.dump(all_conv, f,ensure_ascii=False)


if __name__ == "__main__":
    genrate_corpus(1000, '../table1.json')
#generate_table_schema_json('ad_tbk_dw','rpt_amp_sap_item_action_stat_1d','fbi_industry.json')