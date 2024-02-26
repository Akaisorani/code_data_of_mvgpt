#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Comparison
from sqlparse import tokens
from sqlparse.tokens import Keyword, DML

class Sql_parser(object):
    def __init__(self):
        pass
    
    def is_subselect(self, parsed):
        if not parsed.is_group:
            return False
        for item in parsed.tokens:
            if item.ttype is DML and item.value.upper() == 'SELECT':
                return True
        return False


    def extract_from_part(self, parsed):
        from_seen = False
        for item in parsed.tokens:
            if from_seen:
                if self.is_subselect(item):
                    for x in self.extract_from_part(item):
                        yield x
                elif item.ttype is Keyword:
                    return
                else:
                    yield item
            elif item.ttype is Keyword and item.value.upper() == 'FROM':
                from_seen = True

    def extract_select_part(self, parsed):
        select_seen = False
        for item in parsed.tokens:
            if select_seen:
                if item.ttype is Keyword:
                    return
                else:
                    yield item
            elif item.ttype is Keyword.DML and item.value.upper() == 'SELECT':
                select_seen = True


    def extract_table_identifiers(self, token_stream):
        for item in token_stream:
            if isinstance(item, IdentifierList):
                for identifier in item.get_identifiers():
                    yield (identifier.get_real_name(),identifier.get_alias())
            elif isinstance(item, Identifier):
                yield (item.get_real_name(),item.get_alias())
            # It's a bug to check for Keyword here, but in the example
            # above some tables names are identified as keywords...
            elif item.ttype is Keyword:
                yield (item.value, None)

    def extract_select_identifiers(self, token_stream):
        for item in token_stream:
            if isinstance(item, IdentifierList):
                for identifier in item.get_identifiers():
                    yield self.parse_condition_identifier(identifier)
            elif isinstance(item, Identifier):
                yield self.parse_condition_identifier(item)
            # It's a bug to check for Keyword here, but in the example
            # above some tables names are identified as keywords...
            elif item.ttype is Keyword:
                yield (item.value, None)

    # [("title","t"),...]
    def extract_tables(self, sql):
        stream = self.extract_from_part(sqlparse.parse(sql)[0])
        return list(self.extract_table_identifiers(stream))

    def extract_where_part(self, parsed):
        for item in parsed.tokens:
            if self.is_subselect(item):
                for x in self.extract_where_part(item):
                    yield x
            elif isinstance(item, Where):
                yield item

    def extract_where_join_conditions(self, token_stream):
        for item in token_stream:
            for token in item.tokens:
                # if token.ttype!=tokens.Text.Whitespace and token.ttype!=tokens.Text.Whitespace.Newline:
                #     print(type(token), token.ttype, token.value)

                if isinstance(token, Comparison):
                    # print(token.value)
                    join_condition=self.parse_join_condition(token)
                    if join_condition is not None:
                        yield join_condition

    def extract_where_identifier(self, token_stream):
        for item in token_stream:
            for token in item.tokens:
                # if token.ttype!=tokens.Text.Whitespace and token.ttype!=tokens.Text.Whitespace.Newline:
                #     print(type(token), token.ttype, token.value)

                if isinstance(token, Identifier):
                    ideti=self.parse_condition_identifier(token)
                    yield ideti
                elif isinstance(token, Comparison):
                    # print(token.value)
                    join_condition=self.parse_join_condition_all_the_way(token)
                    if join_condition[0] is not None:
                        yield join_condition[0]
                    if join_condition[1] is not None:
                        yield join_condition[1]

    # ct.id = mc.company_type_id => (("ct","id"),("mc","company_type_id"))
    # return None if not a legal join condition
    def parse_join_condition(self, join_condition):
        identifier1=None
        equal_seen=False
        identifier2=None        
        for token in join_condition.tokens:
            # print(type(token), token.ttype, token.value)
            if identifier1 is None:
                if isinstance(token, Identifier):
                    identifier1=token
            elif equal_seen==False:
                if token.value=="=":
                    equal_seen=True
            elif identifier2 is None:
                if isinstance(token, Identifier):
                    identifier2=token
        
        # print("identifier1", identifier1)
        # print("identifier2", identifier2)
        if identifier1 is None or identifier2 is None:
            return None

        idtf_tup1=self.parse_condition_identifier(identifier1)
        idtf_tup2=self.parse_condition_identifier(identifier2)
        return (idtf_tup1,idtf_tup2)

    def parse_join_condition_all_the_way(self, join_condition):
        identifier1=None
        identifier2=None        
        for token in join_condition.tokens:
            # print(type(token), token.ttype, token.value)
            if identifier1 is None:
                if isinstance(token, Identifier):
                    identifier1=token
            elif identifier2 is None:
                if isinstance(token, Identifier):
                    identifier2=token
        
        # print("identifier1", identifier1)
        # print("identifier2", identifier2)
        idtf_tup1=self.parse_condition_identifier(identifier1) if identifier1 else None
        idtf_tup2=self.parse_condition_identifier(identifier2) if identifier2 else None
        return (idtf_tup1,idtf_tup2)
    
    # identifier ct.id => ("ct","id")
    def parse_condition_identifier(self, identifier):
        if len(identifier.tokens)<3: raise Exception("Identifier token num<3")
        return (identifier.tokens[0].value,identifier.tokens[2].value)

    # join conditions: [(("ct","id"),("mc","company_type_id")),...]
    def extract_join_conditions(self, sql):
        stream = self.extract_where_part(sqlparse.parse(sql)[0])
        if stream is None: return []
        join_condition_stream=self.extract_where_join_conditions(stream)
        # if join_condition_stream is None: return []
        return list(join_condition_stream)

    # identifiers: [("ct","id"),...]
    def extract_identifiers(self, sql):
        stream = self.extract_where_part(sqlparse.parse(sql)[0])
        if stream is None: return []
        identifiers_stream=list(self.extract_where_identifier(stream))
        # if join_condition_stream is None: return []
        return identifiers_stream

    # identifiers: [("ct","id"),...]
    def extract_selects(self, sql):
        stream = self.extract_select_part(sqlparse.parse(sql)[0])
        if stream is None: return []      
        identifiers_stream=list(self.extract_select_identifiers(stream))
        return identifiers_stream

    def split_sqls(self, sqls):
        res=sqlparse.split(sqls)
        res=[x for x in res if x!=""]
        return res

    def get_sql_list_from_file_or_string(self, sqls_string=None, sqls_files=None):
        if isinstance(sqls_files,str):
            sqls_files=[sqls_files]

        sqls=[]

        if not sqls_string:
            for filename in sqls_files:
                with open(filename) as fp:
                    sqls_string=fp.read()
                    sqls.extend(self.split_sqls(sqls_string))
        
        return sqls

    def format(self, sql):
        return sqlparse.format(sql, reindent=True)

    def sql2tokens(self, sql):
        sql=sql.replace("\n"," ")
        sp=sqlparse.parse(sql)
        # print(list(sp[0].flatten()))
        token_lis=[]
        for token in sp[0].flatten():
            if token.ttype is tokens.Text.Whitespace: continue
            # if token.ttype is tokens.Text.Newline: continue
            # print((token.value,token.ttype), end=" ")
            # print(token.value, end=" ")
            token_lis.append(token.value)
        
        return token_lis

if __name__ == '__main__':
    sql = """
        SELECT MIN(mc.note) AS production_note,
            MIN(t.title) AS movie_title,
            MIN(t.production_year) AS movie_year
        FROM company_type AS ct,
            info_type AS it,
            movie_companies AS mc,
            movie_info_idx AS mi_idx,
            title AS t
        WHERE ct.kind = 'production companies'
        AND it.info = 'top 250 rank'
        AND mc.note NOT LIKE '%(as Metro-Goldwyn-Mayer Pictures)%'
        AND (mc.note LIKE '%(co-production)%'
            OR mc.note LIKE '%(presents)%')
        AND ct.id = mc.company_type_id
        AND t.id = mc.movie_id
        AND t.id = mi_idx.movie_id
        AND mc.movie_id = mi_idx.movie_id
        AND it.id = mi_idx.info_type_id;
    """
    sql_line="SELECT MIN(mc.note) AS production_note, MIN(t.title) AS movie_title, MIN(t.production_year) AS movie_year FROM company_type AS ct, info_type AS it, movie_companies AS mc, movie_info_idx AS mi_idx, title AS t WHERE ct.kind = 'production companies' AND it.info = 'top 250 rank' AND mc.note  not like '%(as Metro-Goldwyn-Mayer Pictures)%' and (mc.note like '%(co-production)%' or mc.note like '%(presents)%') AND ct.id = mc.company_type_id AND t.id = mc.movie_id AND t.id = mi_idx.movie_id AND mc.movie_id = mi_idx.movie_id AND it.id = mi_idx.info_type_id;"
    
    sql="""
SELECT ci.role_id,
        ci.person_role_id,
        ci.person_id,
        ci.movie_id,
        cn.country_code,
        cn.name,
        mc.company_id,
        mc.company_type_id,
        mc.note,
        rt.role,
        t.production_year,
        t.episode_nr,
        t.title,
        t.id,
        t.kind_id
FROM cast_info AS ci,
     company_name AS cn,
     movie_companies AS mc,
     role_type AS rt,
     title AS t
WHERE ci.note LIKE '%(producer)%'
  AND cn.country_code = '[ru]'
  AND rt.role = 'actor'
  AND t.id = mc.movie_id
  AND t.id = ci.movie_id
  AND ci.movie_id = mc.movie_id
  AND rt.id = ci.role_id
  AND cn.id = mc.company_id;
  """

    sql_parser=Sql_parser()

    idtf=sql_parser.extract_selects(sql)
    # print(idtf)
    # print(sql_parser.split_sqls(sql))
    # table_lis=sql_parser.extract_tables(sql)
    # join_cond_lis=sql_parser.extract_join_conditions(sql)
    # print(table_lis)
    # print(join_cond_lis)
    # print(sql_parser.format(sql_line))



    # sql2=sql.replace("\n"," ")
    # sql3=sqlparse.format(sql2, use_space_around_operators=True)
    # print(sql3)

    expr="channel in ('1','2','3' )  and conntent_type in ('1','2','3' )  and level in ('1','2','3' )  and period in ('30' )  and shop_id in ('57299763' )  and type in ('2','3','4','5','6','7' ) "
    join_order="((((movie_info_idx as mi_idx cross join info_type as it) cross join movie_companies as mc) cross join company_type as ct) cross join title as t)"
    tks=sql_parser.sql2tokens(join_order)
    print(tks)