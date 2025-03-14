import re

class Predicate(object):
    def __init__(self, identifier, operator, value):
        self.identifier=identifier
        self.operator=operator
        if self.operator=='IN' and isinstance(value, list):
            self.value=value.copy()
            self.value.sort()
        else:
            self.value=value

    @classmethod
    def from_list(cls, predicate_elements):
        if not isinstance(predicate_elements, (tuple, list)) or len(predicate_elements)!=3:
            raise Exception("predicate_elements type error, should be list or tuple with length 3")
        identifier=predicate_elements[0]
        operator=predicate_elements[1]
        if isinstance(predicate_elements[2], list):
            value=predicate_elements[2].copy()
        else:
            value=predicate_elements[2]
        if (operator=='IN' or operator=='in') and isinstance(value, str):
            id_lis=value.strip()[1:-1].split(',')
            id_lis=[x.strip() for x in id_lis]
            id_lis=[x for x in id_lis if x]
            value= id_lis
        if isinstance(value, list):  
            value.sort()
        
        return cls(identifier, operator, value)

    @classmethod
    def from_str(cls, predicate_str):
        # assume predicate is a string
        if not isinstance(predicate_str, str):
            raise Exception("predicate_str type error, should be string")

        # unit: whole, identifier, operator, value
        pred_units=re.findall(r"((new_XXX\.[.|\w]+) (IN|=|>|<|>=|<=|!=) (\(.+?\)|'\w+'|-?\d+))", predicate_str)
        if len(pred_units)==0:
            raise Exception("predicate format error, did not find legal predicate")
        unit=pred_units[0][1:4] # only use the first match, drop others
        # remain value IN clause parse in from_list function, didn't repeat IN clause parse here

        return cls.from_list(unit)

    def __repr__(self):
        return f"Predicate({self.identifier}, {self.operator}, {self.value})"

    def __str__(self):
        if self.operator=='IN':
            value_str="("+", ".join(self.value)+")"
        else:
            value_str=str(self.value)
        return f"{self.identifier} {self.operator} {value_str}"

    def __eq__(self, other):
        if not isinstance(other, Predicate):
            return False
        return self.identifier==other.identifier and self.operator==other.operator and self.value==other.value
    
    def __lt__(self, other):
        if not isinstance(other, Predicate):
            return False
        return self.identifier<other.identifier or (self.identifier==other.identifier and self.operator<other.operator) or (self.identifier==other.identifier and self.operator==other.operator and self.value<other.value)
    
    def __hash__(self):
        return hash((self.identifier, self.operator, tuple(self.value)))
       
    def to_list(self):
        return [self.identifier, self.operator, tuple(self.value)]
    
    def get_db(self):
        return self.identifier.split('.')[0]
    
    def get_table(self):
        return self.identifier.split('.')[1]
    
    def get_column(self):
        return self.identifier.split('.')[2]
  

class Junction(object):
    def __init__(self, predicates=[]):
        self.predicates=predicates
        self.predicates.sort()

    @classmethod
    def from_list(cls, predicates_lis):
        predicates=[]
        for predicate in predicates_lis:
            if isinstance(predicate, Predicate):
                predicates.append(predicate)
            elif isinstance(predicate, (tuple, list)) and len(predicate)==3:
                predicates.append(Predicate.from_list(predicate))
            elif isinstance(predicate, str):
                predicates.append(Predicate.from_str(predicate))
            else:
                raise Exception("predicate type error")
            
        # leave predicates sort to __init__ function

        return cls(predicates)


    def __repr__(self):
        return f"Junction({self.predicates})"

    def __str__(self):
        return " and ".join([str(x) for x in self.predicates])

    def __eq__(self, other):
        if not isinstance(other, Junction):
            return False
        return self.predicates==other.predicates
    
    def __lt__(self, other):
        if not isinstance(other, Junction):
            return False
        return self.predicates<other.predicates

    def __hash__(self):
        return hash(tuple(self.predicates))

    def __contains__(self, predicate):
        return predicate in self.predicates

    def __len__(self):
        return len(self.predicates)

    def is_subset(self, other):
        if not isinstance(other, Junction):
            return False
        for predicate in self.predicates:
            if predicate not in other:
                return False
        return True

    def to_list(self):
        # convert junction to list
        predicates_list=[predicate.to_list() for predicate in self.predicates]
        return predicates_list
    

class Expression(object):
    def __init__(self, junctions=[], exp="", _id =None, origin_junction_strs=[], timestamp=None):
        self.exp_str=exp
        self.junctions=junctions
        self._id=_id
        self.origin_junction_strs=origin_junction_strs
        self.timestamp=timestamp
        
        self.junctions.sort()

    @classmethod
    def from_list(cls, junction_list, exp="", _id =None, origin_junction_strs=[], timestamp=None):
        junctions=[]
        for junction in junction_list:
            if isinstance(junction, Junction):
                junctions.append(junction)
            elif isinstance(junction, (tuple, list)) and len(junction)>0:
                junctions.append(Junction.from_list(junction))
            else:
                print(junction)
                print(type(junction))
                raise Exception("junction type error")
            
        # leave junctions sort to __init__ function

        return cls(junctions, exp, _id, origin_junction_strs=origin_junction_strs, timestamp=timestamp)
    
    @classmethod
    def from_dict(cls, exp_dict):
        # convert exp dict to exp
        junction_list=exp_dict["junctions"]
        exp=exp_dict["exp"]
        _id=exp_dict["_id"]
        return cls.from_list(junction_list, exp, _id)
    
    @classmethod
    def from_str(cls, exp, _id =None, timestamp=None):
        def remove_outer_parenthesis(exp_str):
            # remove outer parenthesis
            exp_str=exp_str.strip()
            if exp_str[0]=='(' and exp_str[-1]==')':
                left_parenthesis_cnt=0
                right_parenthesis_cnt=0
                for i in range(len(exp_str)):
                    if exp_str[i]=='(': left_parenthesis_cnt+=1
                    if exp_str[i]==')': right_parenthesis_cnt+=1
                    if left_parenthesis_cnt==right_parenthesis_cnt:
                        if i==len(exp_str)-1:
                            return remove_outer_parenthesis(exp_str[1:-1])
                        else:
                            return exp_str
            else:
                return exp_str
        

        # assume exp is a string
        if not isinstance(exp, str):
            raise Exception("exp type error, should be string")

        # TODO add parenthesis expression parser to keep structure information (and or)
        pred_units_result=re.findall(r"((new_XXX\.[.|\w]+) (IN|=|>|<|>=|<=|!=) (\(.+?\)|'\w+'|-?\d+))", exp)
        pred_units=[x[1:4] for x in pred_units_result]
        pred_units_ostr=[x[0] for x in pred_units_result]

        # parse identifiers and predicates
        parsed_predicates=[]
        for unit in pred_units:
            # unit: identifier, operator, value
            parsed_predicates.append(Predicate.from_list(unit))
            
        # group predicates by table
        table_junction_dict={}
        for predicate in parsed_predicates:
            table=predicate.get_table()
            if table not in table_junction_dict:
                table_junction_dict[table]=[]
            table_junction_dict[table].append(predicate)
        
        parsed_junction_lis=list(table_junction_dict.values())

        # process pred_units_ostr, split exp into continuous sub expression str, (contains parenthesis, or)
        origin_junction_strs=[]
        rest_exp=remove_outer_parenthesis(exp.strip())
        # split rest_exp into segment_lis
        segment_lis=[]
        segment_type=[]
        left_parenthesis_cnt=0
        right_parenthesis_cnt=0
        for index, (predicate_str, parsed_predicate) in enumerate(zip(pred_units_ostr, parsed_predicates)):
            pos=rest_exp.find(predicate_str)
            if pos==-1:
                print("rest_exp", rest_exp)
                print("predicate_str", predicate_str)
                raise Exception("predicate_str not found in rest_exp")
            if pos>0:
                for i in range(pos):
                    segment_lis.append(rest_exp[i])
                    segment_type.append("others")
                    if rest_exp[i]=='(': left_parenthesis_cnt+=1
                    if rest_exp[i]==')': right_parenthesis_cnt+=1
            segment_lis.append(predicate_str)
            segment_type.append("predicate")
            rest_exp=rest_exp[pos+len(predicate_str):]

            if index>0 and parsed_predicates[index].get_table()!=parsed_predicates[index-1].get_table():
                # reach a new table predicate, construct previous table expression, begin and end with predicate
                endpos=len(segment_lis)-2
                p_r_cnt=right_parenthesis_cnt
                p_l_cnt=left_parenthesis_cnt
                clostest_lp_pos=len(segment_lis)-1
                while endpos>=0 and segment_type[endpos]!="predicate" and segment_lis[endpos]!=")":
                    if segment_lis[endpos]=='(':
                        p_l_cnt-=1
                        clostest_lp_pos=endpos
                    endpos-=1
                beginpos=0
                while beginpos<len(segment_lis) and p_l_cnt>p_r_cnt: 
                    if segment_lis[beginpos]=='(': p_l_cnt-=1
                    beginpos+=1
                
                contructed_junction_str="".join(segment_lis[beginpos:endpos+1])
                contructed_junction_str=remove_outer_parenthesis(contructed_junction_str)
                origin_junction_strs.append(contructed_junction_str)
                # remove used part
                if clostest_lp_pos!=-1:
                    endpos=clostest_lp_pos-1
                segment_lis=segment_lis[:beginpos]+segment_lis[endpos+1:]
                segment_type=segment_type[:beginpos]+segment_type[endpos+1:]
                right_parenthesis_cnt-=p_r_cnt
                left_parenthesis_cnt-=p_l_cnt
            elif index==len(pred_units_ostr)-1:
                # reach last predicate, construct last table expression, begin and end with predicate
                # first parse rest exp
                for i in range(len(rest_exp)):
                    segment_lis.append(rest_exp[i])
                    segment_type.append("others")
                    if rest_exp[i]=='(': left_parenthesis_cnt+=1
                    if rest_exp[i]==')': right_parenthesis_cnt+=1
                
                endpos=len(segment_lis)-1
                p_r_cnt=right_parenthesis_cnt
                p_l_cnt=left_parenthesis_cnt
                clostest_lp_pos=len(segment_lis)-1
                while endpos>=0 and segment_type[endpos]!="predicate" and segment_lis[endpos]!=")":
                    if segment_lis[endpos]=='(':
                        p_l_cnt-=1
                        clostest_lp_pos=endpos
                    endpos-=1
                beginpos=0
                while beginpos<len(segment_lis) and p_l_cnt>p_r_cnt: 
                    if segment_lis[beginpos]=='(': p_l_cnt-=1
                    beginpos+=1

                contructed_junction_str="".join(segment_lis[beginpos:endpos+1])
                contructed_junction_str=remove_outer_parenthesis(contructed_junction_str)
                origin_junction_strs.append(contructed_junction_str)
                # remove used part
                if clostest_lp_pos!=-1:
                    endpos=clostest_lp_pos-1
                segment_lis=segment_lis[:beginpos]+segment_lis[endpos+1:]
                segment_type=segment_type[:beginpos]+segment_type[endpos+1:]
                right_parenthesis_cnt-=p_r_cnt
                left_parenthesis_cnt-=p_l_cnt

        return cls.from_list(parsed_junction_lis, exp, _id, origin_junction_strs=origin_junction_strs, timestamp=timestamp)


    def __repr__(self):
        return f"Expression({self.junctions})"

    def __str__(self):
        return " or ".join([str(x) for x in self.junctions])

    def __eq__(self, other):
        if not isinstance(other, Expression):
            return False
        return self.is_equal(other)
    
    def __lt__(self, other):
        if not isinstance(other, Expression):
            return False
        return self.junctions<other.junctions

    def __hash__(self):
        return hash(tuple(self.junctions))

    def __contains__(self, junction):
        return junction in self.junctions

    def __len__(self):
        return len(self.junctions)

    def is_subset(self, other):
        if not isinstance(other, Expression):
            return False
        for junction in self.junctions:
            if junction not in other:
                return False
        return True

    def is_superset(self, other):
        if not isinstance(other, Expression):
            return False
        return other.is_subset(self)

    def is_equal(self, other):
        return self.is_subset(other) and self.is_superset(other)

    def is_intersect(self, other):
        if not isinstance(other, Expression):
            return False
        for junction in self.junctions:
            if junction in other:
                return True
        return False

    def intersection(self, other):
        if not isinstance(other, Expression):
            return False
        junctions=[]
        for junction in self.junctions:
            if junction in other:
                junctions.append(junction)
        return Expression(junctions)

    def union(self, other):
        if not isinstance(other, Expression):
            return False
        junctions=[]
        for junction in self.junctions:
            junctions.append(junction)
        for junction in other.junctions:
            if junction not in self:
                junctions.append(junction)
        return Expression(junctions)

    def difference(self, other):
        if not isinstance(other, Expression):
            return False
        junctions=[]
        for junction in self.junctions:
            if junction not in other:
                junctions.append(junction)
        return Expression(junctions)
    

    def to_dict(self):
        # convert exp to dict
        junction_list=[junction.to_list() for junction in self.junctions]
        return {"junctions": junction_list, "exp": self.exp_str, "_id": self._id}




