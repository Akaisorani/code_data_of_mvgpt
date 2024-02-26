import csv
import os
import pandas as pd
import time
import copy
from expression import Predicate, Junction, Expression

class MaterializedView_collection(object):
    def __init__(self):
        self.mvs=[]
        self.create_times=[]
        self.mvs_index_by_junction={}
        self.hit_num=dict()

    def add_mvs(self, mvs, create_times):
        if not isinstance(mvs, list):
            raise Exception("mvs type error, should be list")

        success_added=[]
        for mv, create_time in zip(mvs, create_times):
            ret=self.add_mv(mv, create_time)
            if ret: success_added.append(mv)
        return success_added

    def add_mv(self, mv, create_time, hit_num=0):
        # add mv to self.mvs and build index
        if isinstance(mv, Expression):
            pass
        elif isinstance(mv, str):
            mv=Expression.from_str(mv)
        else:
            raise Exception("mv type error, should be Expression or str")

        success_added=False
        if mv not in self.hit_num:
            self.mvs.append(mv)
            self.create_times.append(create_time)
            self.hit_num[mv]=hit_num
            success_added=True
        
            for junction in mv.junctions:
                if junction not in self.mvs_index_by_junction:
                    self.mvs_index_by_junction[junction]=[]
                self.mvs_index_by_junction[junction].append(mv)
        elif hit_num!=0:
            self.hit_num[mv]+=hit_num
            success_added=True

        return success_added
        

    def match_mvs(self, query):
        # query is a expression
        if not isinstance(query, Expression):
            raise Exception("query type error, should be Expression")
        matched_mvs=set()
        for junction in query.junctions:
            if junction in self.mvs_index_by_junction:
                for mv in self.mvs_index_by_junction[junction]:
                    if mv.is_subset(query):
                        matched_mvs.add(mv)

        return list(matched_mvs)
    
    def add_hit(self, mvs):
        if not isinstance(mvs, list):
            raise Exception("mvs type error, should be list")
        for mv in mvs:
            self.hit_num[mv]+=1

    def add_mv_collection(self, other):
        if not isinstance(other, MaterializedView_collection):
            raise Exception("mv_collection type error, should be MaterializedView_collection")
        for mv, create_time in zip(other.mvs, other.create_times):
            self.add_mv(mv, create_time, other.hit_num[mv])

    
class Workload(object):
    def __init__(self):
        self.timestamps=[]
        self.queries=[]
        self.hit_flag=[]

    def add_queries(self, queries, timestamps=None):
        if not isinstance(queries, list):
            raise Exception("queries type error, should be list")    
        if timestamps is not None and isinstance(timestamps, (int, float)):
            timestamps=[timestamps]*len(queries)
        elif timestamps is not None and isinstance(timestamps, list):
            if len(timestamps)!=len(queries):
                raise Exception("timestamps length error, should equal to queries length")
        else:
            timestamps=[None]*len(queries)
        
        self.queries.extend(queries)
        self.timestamps.extend(timestamps)
    
    def execute_queries(self, mvs, start_timestamp=None, end_timestamp=None):
        if not isinstance(mvs, MaterializedView_collection):
            raise Exception("mvs type error, should be MaterializedView_collection")
        self.hit_flag=[]
        exe_num=0
        for timestamp, query in zip(self.timestamps, self.queries):
            # [start_timestamp, end_timestamp)
            if start_timestamp is not None and timestamp<start_timestamp: continue
            if end_timestamp is not None and timestamp>=end_timestamp: continue
            exe_num+=1
            matched_mvs=mvs.match_mvs(query)
            if len(matched_mvs)>0:
                self.hit_flag.append(1)
                mvs.add_hit(matched_mvs)
            else:
                self.hit_flag.append(0)
        hit_num=sum(self.hit_flag)

        result={
            "exe_num": exe_num,
            "hit_num": hit_num,
            "hit_flag": self.hit_flag
        }
        
        return result
        
