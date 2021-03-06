# -*- coding: UTF-8 -*-
#/**
# * Software Name : libmich 
# * Version : 0.2.3
# *
# * Copyright � 2014. Benoit Michau. ANSSI.
# *
# * This program is free software: you can redistribute it and/or modify
# * it under the terms of the GNU General Public License version 2 as published
# * by the Free Software Foundation. 
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# * GNU General Public License for more details. 
# *
# * You will find a copy of the terms and conditions of the GNU General Public
# * License version 2 in the "license.txt" file or
# * see http://www.gnu.org/licenses/ or write to the Free Software Foundation,
# * Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
# *
# *--------------------------------------------------------
# * File Name : asn1/parsers.py
# * Created : 2014-10-08
# * Authors : Benoit Michau 
# *--------------------------------------------------------
#*/

from utils import *
import ASN1

#------------------------------------------------------------------------------#
# ASN.1 formal parameters parser
#------------------------------------------------------------------------------#
# 1st potential syntactic element after object ASN.1 object name

def parse_param(Obj, text=''):
    '''
    parses formal parameters provided in ASN.1 object definition
    
    sets an OrderedDict of (name : {type, val}) in Obj['param'] 
        if parameters are found, None otherwise
    
    returns the rest of the text
    '''
    # 'INTEGER:test, GrosTest : grosTest, Grostest'
    # list of Type:name or just TypeRef as name, coma-separated
    text, text_param = extract_curlybrack(text)
    if not text_param:
        return text
    #
    # check for "," separator
    coma_offsets = [-1] + search_top_lvl_sep(text_param, ',') + [len(text_param)]
    params = map(stripper, [text_param[coma_offsets[i]+1:coma_offsets[i+1]] \
                              for i in range(len(coma_offsets)-1)])
    #
    P = OD()
    for param in params:
        m = SYNT_RE_PARAM.match(param)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid formal parameter: %s'\
                  % (Obj.get_fullname(), param)))
        if m.group(2) is None:
            # no param governor:
            # parameter value: type (or class)
            P[m.group(1)] = {'type':None,
                             'ref':[]}
        else:
            # param governor: type (or class)
            # parameter value: lower-case 1st letter -> value
            #                  upper-case 1st letter -> set
            if m.group(1) in SYNT_BASIC_TYPES:
                param_obj = ASN1.ASN1Obj(name=m.group(2), 
                                         mode=0, 
                                         type=m.group(1))
            elif m.group(1) in GLOBAL.TYPE:
                param_obj = GLOBAL.TYPE[m.group(1)]
            else:
                raise(ASN1_PROC_LINK('%s: undefined type %s in parameters'\
                      % (Obj.get_fullname(), m.group(1))))
            try:
                P[m.group(2)] = {'type':param_obj,
                                 'ref':[]}
            except:
                raise(ASN1_PROC_TEXT('%s: duplicated parameter: %s'\
                      % (Obj.get_fullname(), m.group(2))))
        #
        rest = param[m.end():].strip()
        if SYNT_RE_REMAINING.search(rest):
            raise(ASN1_PROC_TEXT('%s: unparsed formal parameter syntax: %s'\
                  % (Obj.get_fullname(), param)))
    #
    assert(len(P) > 0)
    Obj['param'] = P
    return text

#------------------------------------------------------------------------------#
# ASN.1 standard definition
#------------------------------------------------------------------------------#
def parse_definition(Obj, text=''):
    # the standard parser dispatcher (which depends from Obj['type']) 
    # is provided by Obj
    return Obj.parse_definition(text)

#------------------------------------------------------------------------------#
# ASN.1 tag parser
#------------------------------------------------------------------------------#
def parse_tag(Obj, text=''):
    '''
    parses the potential tag within "[" and "]" 
    with potential class directive inside (UNIVERSAL, APPLICATION, ...)
    and potential inlined tagging mode (IMPLICIT / EXPLICIT)
    
    sets a 3-tuple (value, class, mode), or None, in Obj['tag']
    
    returns the rest of the text
    '''
    m = SYNT_RE_TAG.match(text)
    if not m:
        # no tag specified
        Obj['tag'] = None
        return text
    cla, val_num, val_ref = m.group(1), m.group(2)
    if cla is None:
        cla = TAG_CONTEXT_SPEC
    if val_ref:
        if val_ref not in GLOBAL.VALUE \
        or GLOBAL.VALUE[val_ref]['type'] != TYPE_INTEGER:
            raise(ASN1_PROC_LINK('%s: undefined value %s for tag'\
                  % (Obj.get_fullname(), val_ref)))
        val_num = GLOBAL.VALUE[val_ref]['val']
    text = text[m.end():].strip()
    m = re.match('IMPLICIT|EXPLICIT', text)
    if not m:
        Obj['tag'] = (val_num, cla, None)
    else:
        Obj['tag'] = (val_num, cla, m.group())
        text = text[m.end():].strip()
    #
    return text

#------------------------------------------------------------------------------#
# ASN.1 type parser
#------------------------------------------------------------------------------#
# WNG: because of SEQUENCE OF / SET OF syntax
# this function can early-call constraints parsing functions:
# parse_constraint_size() or parse_constraint_integer()

def parse_type(Obj, text=''):
    '''
    parses the type (or class) of the ASN.1 object
    
    sets the basic type str in Obj['type']
    sets potential Obj['typeref'], Obj['cont'], Obj['const'] if type is 
    a reference to another user-defined type
    
    returns the rest of the text
    '''
    #
    # 1) reference to an ASN.1 basic type
    m = match_basic_type(text)
    if m:
        Obj['type'] = m
        text = text[len(m):].strip()
        # for SEQUENCE OF / SET OF, parse further SIZE constraint and OF keyword
        if Obj['type'] in (TYPE_SEQ, TYPE_SET):
            # get potential SIZE constraint and OF keyword
            m = re.match('(\({0,1}\s{0,}SIZE)|(OF)', text)
            if m and m.group(1) is not None:
                # get SIZE constraint
                if m.group(1)[0] == '(':
                    text = parse_constraint_size(Obj, text)
                else:
                    text = text[4:].strip()
                    text = parse_constraint_integer(Obj, text)
                    #Obj['const'][-1]['type'] = CONST_SIZE
                if text[:2] != 'OF':
                    # SIZE constraint only for SEQ / SET OF
                    raise(ASN1_PROC_TEXT('%s: invalid SEQUENCE / SET with SIZE: %s'\
                          % (Obj.get_fullname(), text)))
                # OF keyword
                Obj['type'] = '%s OF' % Obj['type']
                text = text[2:].strip()
            elif m and m.group(2):
                # no SIZE constraint, just OF keyword
                Obj['type'] = '%s OF' % Obj['type']
                text = text[2:].strip()
        return text
    #
    # 2) reference to a user-defined CLASS field: CLASSNAME.&classField
    m = SYNT_RE_CLASSREF.match(text)
    if m:
        cla, cla_field = m.group(2), m.group(3)
        # check for CLASSNAME existence
        if cla not in GLOBAL.TYPE:
            # TODO: this could be a CLASS type parameterization
            # lookup against parameters should be implemented
            raise(ASN1_PROC_LINK('%s: undefined CLASS %s' % (obj['name'], cla)))
        # check for class field existence
        elif cla_field not in GLOBAL.TYPE[cla]['cont']:
            raise(ASN1_PROC_TEXT('%s: CLASS %s, invalid field %s'\
                  % (obj['name'], cla, cla_field)))
        # if typeref is referring to a parameterized type, a clone is required
        typeref = GLOBAL.TYPE[cla]['cont'][cla_field]
        if typeref.get_param() is not None:
            Obj['typeref'] = typeref.clone()
        else:
            Obj['typeref'] = typeref.clone_const()
        Obj['type'] = Obj['typeref']['type']
        #Obj['tag'] = Obj['typeref']['tag'] # TODO: to be verified
        Obj['ext'] = Obj['typeref']['ext']
        Obj['cont'] = Obj['typeref']['cont']
        Obj['const'] = Obj['typeref']['const']
        # WNG: seems OK to not copy flags, as it is specific to components
        #Obj['flags'] = Obj['typeref']['flags']
        Obj['syntax'] = Obj['typeref']['syntax']
        if Obj['type'] in (TYPE_SEQ, TYPE_SET, TYPE_CLASS):
            Obj._build_constructed_rootext()
        return text[m.end():].strip()
    #
    # 3) reference to a user-defined Type
    m = SYNT_RE_TYPEREF.match(text)
    if m:
        typeref = m.group(1)
        # check for Type existence
        if typeref not in GLOBAL.TYPE:
            # TODO: this could be a Type parameterization
            # lookup against parameters should be implemented
            raise(ASN1_PROC_LINK('%s: undefined Type %s'\
                  % (Obj.get_fullname(), typeref)))
        # if typeref is referring to a parameterized type, a clone is required
        typeref = GLOBAL.TYPE[typeref]
        if typeref.get_param() is not None:
            Obj['typeref'] = typeref.clone()
        else:
            Obj['typeref'] = typeref.clone_const()
        Obj['type'] = Obj['typeref']['type']
        #Obj['tag'] = Obj['typeref']['tag'] # TODO: to be verified
        Obj['ext'] = Obj['typeref']['ext']
        Obj['cont'] = Obj['typeref']['cont']
        Obj['const'] = Obj['typeref']['const']
        # WNG: seems OK to not copy flags, as it is specific to components
        #Obj['flags'] = Obj['typeref']['flags']
        Obj['syntax'] = Obj['typeref']['syntax']
        if Obj['type'] in (TYPE_SEQ, TYPE_SET, TYPE_CLASS):
            Obj._build_constructed_rootext()
        return text[m.end():].strip()
    #
    raise(ASN1_PROC_TEXT('%s: invalid ASN.1 type %s' % (Obj.get_fullname(), text)))

#------------------------------------------------------------------------------#
# ASN.1 content parser
#------------------------------------------------------------------------------#

def parse_content_integer(Obj, text=''):
    '''
    parses named numbers in "{" "}" in INTEGER definition
    
    sets an ordered dict of named numbers (name:value), or None, in Obj['cont']
    
    returns the rest of the text
    '''
    # 'alpha(-1), beta (deux), trois(dreI-3), four( 4 ), five ( fifthValue)'
    # list of name(value), coma-separated
    text, text_cont = extract_curlybrack(text)
    if text_cont is None:
        return text
    #
    named_numbers = map(stripper, text_cont.split(','))
    cont = OD()
    for nn in named_numbers:
        m = SYNT_RE_INT_ID.match(nn)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid named number: %s'\
                  % (Obj.get_fullname(), text_cont)))
        if m.group(4):
            # integer value reference
            if m.group(4) not in GLOBAL.VALUE:
                raise(ASN1_PROC_LINK('%s: undefined INTEGER reference: %s'\
                      % (Obj.get_fullname(), m.group())))
            elif GLOBAL.VALUE[m.group(4)]['type'] != TYPE_INTEGER:
                raise(ASN1_PROC_TEXT('%s: INTEGER reference to bad type: %s'\
                      % (Obj.get_fullname(), m.group())))
            val_num = GLOBAL.VALUE[m.group(4)]['val']
        else:
            val_num = int(m.group(3))
        try:
            cont[m.group(1)] = val_num
        except:
            raise(ASN1_PROC_TEXT('%s: duplicated named number: %s'\
                  % (Obj.get_fullname(), text_cont)))
    if cont:
        Obj['cont'] = cont
    #
    return text

def parse_content_enum(Obj, text=''):
    '''
    parses enumeration content in "{" "}" in ENUMERATED definition
    
    sets an OrderedDict (name : index) in Obj['cont'] for all root and extended 
        components, and list extended component in Obj['ext'],
        according to the module extensibility option
    
    returns the rest of the text
    '''
    # 'alpha(1), beta , trois(dreI-3), four, ..., five ( fifthValue)'
    # list of enumerations, coma-separated
    text, text_cont = extract_curlybrack(text)
    if text_cont is None:
        return text
    enums = map(stripper, text_cont.split(','))
    #
    # index and index_used are to complete value of unindexed enums
    index = 0
    index_used = []
    O = OD()
    for enum in enums:
        m = SYNT_RE_ENUM.match(enum)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid enumeration: %s'\
                  % (Obj.get_fullname(), enum)))
        if m.group(4):
            # integer value reference for index
            if m.group(4) not in GLOBAL.VALUE:
                raise(ASN1_PROC_LINK('%s: undefined INTEGER reference: %s'\
                      % (Obj.get_fullname(), enum)))
            elif GLOBAL.VALUE[m.group(4)]['type'] != TYPE_INTEGER:
                raise(ASN1_PROC_TEXT('%s: INTEGER reference to bad type: %s'\
                      % (Obj.get_fullname(), enum)))
            ind_num = GLOBAL.VALUE[m.group(4)]['val']
        elif m.group(3):
            ind_num = int(m.group(3))
        else:
            # no index value provided: create one
            while index in index_used:
                index += 1
            ind_num = index
        try:
            O[m.group(1)] = ind_num
        except:
            raise(ASN1_PROC_TEXT('%s: duplicated enumeration: %s'\
                  % (Obj.get_fullname(), text_cont)))
        else:
            index_used.append( ind_num )
    #
    Obj['cont'] = OD()
    ext_in = False
    # check against extensibility option
    if MODULE_OPT.EXT or '...' in O.keys():
        Obj['ext'] = []
    for key, val in O.items():
        if key == '...':
            ext_in = True
        else:
            Obj['cont'][key] = val
            if ext_in:
                Obj['ext'].append(key)
    #
    return text

def parse_content_bitstr(Obj, text=''):
    '''
    parses named bits in "{" "}" in BIT STRING definition
    
    sets an ordered dict of named bits (name:position), or None, in Obj['cont']
    
    returns the rest of the text
    '''
    return parse_content_integer(Obj, text)

def parse_content_constructed(Obj, text=''):
    '''
    parses all internal definition in "{" "}" for SEQUENCE / SET / CHOICE definitions
    
    sets an OrderedDict (name : ASN1Obj) in Obj['cont'] for all root and extended 
        components, and list extended component in Obj['ext'],
        according to the module extensibility option
    
    for SEQUENCE OF / SET OF definition, sets directly Obj['cont'] 
        with a single ASN1Obj
    
    returns the rest of the text
    '''
    if Obj['type'] in (TYPE_SEQ_OF, TYPE_SET_OF):
        Obj['cont'] = ASN1.ASN1Obj(mode=0,
                                   name='_cont_',
                                   parent=Obj)
        return parse_definition(Obj['cont'], text)
    #
    # otherwise, it's inside { }
    text, text_cont = extract_curlybrack(text)
    if text_cont is None:
        return text
    # sequence of components
    _process_components(Obj, text_cont)
    #
    return text

def _process_components(Obj, text=''):
    coma_offsets = [-1] + search_top_lvl_sep(text, ',') + [len(text)]
    components = map(stripper, [text[coma_offsets[i]+1:coma_offsets[i+1]] \
                                for i in range(len(coma_offsets)-1)])
    #
    Cont, Ext = OD(), None
    in_ext = False # extension handling
    in_group, group_num = False, 0 # grouped extension handling
    #
    for comp in components:
        #
        m = re.match('COMPONENTS\s{1,}OF', comp)
        if m:
            # reference to constructed content: process to substitution
            if in_ext:
                raise(ASN1_PROC_TEXT('%s: invalid SEQUENCE reference in '\
                      'extension: %s' % (Obj.get_fullname(), comp)))
            comp = comp[m.end():].strip()
            # get typeref
            if comp not in GLOBAL.TYPE:
                raise(ASN1_PROC_LINK('%s: undefined SEQUENCE reference: %s'\
                      % (Obj.get_fullname(), comp)))
            elif GLOBAL.TYPE[comp]['type'] != TYPE_SEQ:
                raise(ASN1_PROC_TEXT('%s: SEQUENCE reference to bad type: %s'\
                      % (Obj.get_fullname(), comp)))
            # collect all root / extended content from the typeref
            for name in GLOBAL.TYPE[comp]['cont']:
                Cont[name] = GLOBAL.TYPE[comp]['cont'][name]
            comp = ''
        #
        else:
            if comp[:2] == '[[' and comp[-2:] == ']]':
                if not in_ext:
                    raise(ASN1_PROC_TEXT('%s: invalid group marker: %s'\
                          % (Obj.get_fullname(), comp)))
                # grouped extension
                # the sequence of components is in extension, in a given group
                in_group = True
                comp = comp[2:-2].strip()
                #
                #log(comp)
                _process_components(Obj, comp)
                if Obj['ext'] is not None:
                    raise(ASN1_PROC_TEXT('%s: invalid extension marker within '\
                          'extension group: %s' % (Obj.get_fullname(), comp)))
                for c in Obj['cont']:
                    Cont[c] = Obj['cont'][c]
                    Cont[c]['group'] = group_num
                Ext.append( Obj['cont'].keys() )
                #
                Obj['cont'] = None
                comp = ''
                in_group = False
                group_num += 1
            #
            else:
                m = SYNT_RE_IDENT.match(comp)
                if m:
                    # single identified component
                    name = m.group(1)
                    comp = comp[m.end():].strip()
                    Cont[name] = ASN1.ASN1Obj(name=name,
                                              mode=0,
                                              parent=Obj)
                    # the component is in extension, but not part of any group
                    Cont[name]['group'] = -1
                    if in_ext:
                        Ext.append(name)
                    comp = parse_definition(Cont[name], comp)
                #
                elif comp == '...':
                    # moving to extended content
                    Ext = []
                    in_ext = True
                    comp = comp[3:].strip()
        #
        if comp:
            raise(ASN1_PROC_TEXT('%s: invalid constructed component: %s'\
                  % (Obj.get_fullname(), comp)))
    #
    # check against extensibility option
    if Ext is None and MODULE_OPT.EXT:
        Ext = []
    #
    Obj['cont'], Obj['ext'] = Cont, Ext

def parse_flags(Obj, text=''):
    '''
    parses constructed types / class specific flags: UNIQUE, OPTIONAL, DEFAULT
    
    sets the flag in Obj['flags']
    
    returns the rest of the text
    '''
    text_new = _parse_flag(Obj, text)
    while text_new != text:
        text = text_new
        text_new = _parse_flag(Obj, text)
    return text_new

def _parse_flag(Obj, text=''):
    if Obj['parent'] and Obj['parent']['type'] == TYPE_CLASS \
    and text[:6] == 'UNIQUE':
        if Obj['flags'] is None:
            Obj['flags'] = {}
        Obj['flags'].update({FLAG_UNIQ:None})
        return text[6:].strip()
    elif text[:8] == 'OPTIONAL':
        if Obj['flags'] is None:
            Obj['flags'] = {}
        Obj['flags'].update({FLAG_OPT:None})
        return text[8:].strip()
    elif text[:7] == 'DEFAULT':
        if Obj['flags'] is None:
            Obj['flags'] = {}
        # TODO: associated type value parsing
        Obj['flags'].update({FLAG_DEF: text[7:].strip()})
        text = text[7:]
        assert( Obj['val'] is None )
        assert( Obj['mode'] == 0 )
        text = parse_value(Obj, text)
        Obj['flags'].update({FLAG_DEF: Obj['val']})
        Obj['val'] = None
        return text
    else:
        return text

def parse_content_class(Obj, text=''):
    '''
    parses all internal definition in "{" "}" in CLASS definition
    
    sets an OrderedDict (name : ASN1Obj) in Obj['cont']
    
    returns the rest of the text
    '''
    # there is no nested CLASS
    if Obj['parent']:
        raise(ASN1_PROC_TEXT('%s: please, no nested CLASS'\
              % Obj.get_fullname())) 
    text, text_cont = extract_curlybrack(text)
    if text_cont is None:
        return text
    # sequence of fields
    _process_fields(Obj, text_cont)
    #
    return text

def _process_fields(Obj, text=''):
    coma_offsets = [-1] + search_top_lvl_sep(text, ',') + [len(text)]
    fields = map(stripper, [text[coma_offsets[i]+1:coma_offsets[i+1]] \
                                for i in range(len(coma_offsets)-1)])
    #
    Cont = OD()
    for field in fields:
        #
        m = SYNT_RE_FIELD_IDENT.match(field)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid CLASS field: %s'\
                  % (Obj.get_fullname(), field)))
        name = m.group(1)
        Cont[name] = ASN1.ASN1Obj(name=name,
                                  mode=0,
                                  parent=Obj)
        field = field[m.end():].strip()
        #
        # OPEN TYPE
        if re.match('[A-Z]', name):
            Cont[name]['type'] = TYPE_OPEN
            field = parse_flags(Cont[name], field)
        #
        # basic type or TypeRef
        else:
            field = parse_definition(Cont[name], field)
        #
        if field:
            raise(ASN1_PROC_NOSUPP('%s: unsupported CLASS field definition: %s'\
                  % (Obj.get_fullname(), field)))
    #
    Obj['cont'] = Cont 

def parse_syntax(Obj, text=''):
    '''
    parses all internal naming convention in "{" "}" in WITH SYNTAX declaration
    
    sets an OrderedDict (syntax : (name, group)) in Obj['syntax'], or None
    
    returns the rest of the text
    '''
    # start with WITH SYNTAX
    m = re.match('WITH\s{1,}SYNTAX', text)
    if not m:
        return text
    #
    text = text[m.end():].strip()
    text, text_synt = extract_curlybrack(text)
    if text_synt is None:
        raise(ASN1_PROC_TEXT('%s: invalid CLASS WITH SYNTAX declaration: %s'\
              % (Obj['name'], text)))
    #
    synt = OD()
    group_state, group_num = None, 0
    # get all the SYNTAX text until there is a &fieldIdent
    # check for optional groups in "[" "]"
    # TODO: handle nested optional groups, e.g. [ A [B]] C
    m_gr = re.match('\[', text_synt)
    if m_gr:
        group_state = group_num
        text_synt = text_synt[1:].strip()
    m = SYNT_RE_FIELD_IDENT.search(text_synt)
    while m:
        synt[text_synt[:m.start()].strip()] = (m.group(1), group_state)
        text_synt = text_synt[m.end():].strip()
        m_gr = re.match('\]', text_synt)
        if m_gr:
            group_state = None
            group_num += 1
            text_synt = text_synt[1:].strip()
        m_gr = re.match('\[', text_synt)
        if m_gr:
            group_state = group_num
            text_synt = text_synt[1:].strip()
        m = SYNT_RE_FIELD_IDENT.search(text_synt)
    if SYNT_RE_REMAINING.match(text_synt):
        raise(ASN1_PROC_TEXT('%s: remaining CLASS syntax: %s'\
              % (Obj['name'], text_synt)))
    #
    if synt:
        Obj['syntax'] = synt
    return text

def parse_content_subtype(Obj, text=''):
    '''
    parses content in "{" "}" in user-defined ASN.1 sub-subtype
    
    sets the given values to the parameters' referrer elements of Obj
    
    returns the rest of the text
    '''
    #
    text, text_cont = extract_curlybrack(text)
    if text_cont is None:
        return text
    #
    coma_offsets = [-1] + search_top_lvl_sep(text_cont, ',') + [len(text_cont)]
    args = map(stripper, [text_cont[coma_offsets[i]+1:coma_offsets[i+1]] \
                                    for i in range(len(coma_offsets)-1)])
    #
    param_cnt = 0
    for arg in args:
        # extract parameters passed in { }
        # this is bad, as those { } have the meaning that the arg is a reference
        # to an existing object that won't require parsing        
        m = SYNT_RE_PARAM_ARG.match(arg)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid content argument: %s'\
                  % (Obj['name'], arg)))
        if m.group(2) is not None:
            # object info set reference: {param}, ... 
            _process_arg(Obj, param_cnt, m.group(2), val_set=True)
        else:
            # value: param, ...
            _process_arg(Obj, param_cnt, m.group(1), val_set=False)
        param_cnt += 1
    #
    return text

def _process_arg(Obj, cnt, arg, val_set=False):
    # arg can be a value -> set it to all the referrers
    #            a ref to a value / set -> get it and set it to all the referrers
    #            a ref to a parameter -> set all the referrers in Obj['param']
    try:
        param_gov = Obj['typeref']['param'].values()[cnt]['type']
        param_ref = Obj['typeref']['param'].values()[cnt]['ref']
    except:
        raise(ASN1_PROC_TEXT('%s: invalid subtype content: %s'\
              %(Obj.get_fullname(), arg)))
    if not param_ref:
        raise(ASN1_PROC_TEXT('%s: invalid parameter destination'\
              % Obj.get_fullname()))
    #
    # 1) if arg is corresponding to a parameter, 
    # just update the parameter referrer
    Obj_param = Obj.get_param()
    if Obj_param and arg in Obj_param:
        # update the referrer path in Obj_param:
        Obj_param[arg]['ref'] = []
        for (p, b) in param_ref:
            Obj_param[arg]['ref'].append((Obj.get_parent_path()+p, b))
        return
    #
    # 2) if arg is setting a value / set / type
    if param_gov is not None:
        # 2.a) if there is a param governor, use it to parse the value / set
        assert( param_gov['val'] is None )
        assert( param_gov['mode'] == 0 )
        if val_set:
            param_gov['mode'] = 2
            arg = '{%s}' % arg
            parse_set(param_gov, arg)
        else:
            param_gov['mode'] = 1
            parse_value(param_gov, arg)
        _dispatch_param_val(Obj, param_ref, param_gov)
        # restore param_gov as a standard Type object
        param_gov['val'] = None
        param_gov['mode'] = 0
    else:
        # 2.b) if there is no param governor, arg is a type
        param_obj = ASN1.ASN1Obj(mode=0)
        parse_definition(param_obj, arg)
        _dispatch_param_val(Obj, param_ref, param_obj)
    #

def _dispatch_param_val(Obj, param_ref, val_obj):
    # set the value (or whole value object) to all referrers to the parameter
    for (p, b) in param_ref:
        dst_obj = Obj
        for r in p:
            dst_val = dst_obj[r]
            if r == p[-1]:
                break
            dst_obj = dst_val
        # end of the path
        if b:
            # set a clone of the entire ASN1Obj
            dst_obj[r] = val_obj.clone_light()
        else:
            # set just the value
            dst_obj[r] = val_obj['val']

#------------------------------------------------------------------------------#
# ASN.1 value parser
#------------------------------------------------------------------------------#
# TODO: value parsing for constructed types is not supported yet...
# TODO: there is currently no constraint checking when parsing values

def parse_value(Obj, text=''):
    # the standard parser dispatcher (which depends from Obj['type']) 
    # is provided by Obj
    return Obj.parse_value(text)

def parse_value_null(Obj, text=''):
    # test NULL ::= NULL
    m = re.match('NULL', text)
    if not m:
        # so this must be a global identifier reference
        m = SYNT_RE_IDENT.match(text)
        if not m:        
            raise(ASN1_PROC_TEXT('%s: invalid NULL value: %s'\
                  % (Obj.get_fullname(), text)))
        ref = m.group()
        if ref not in GLOBAL.VALUE:
            raise(ASN1_PROC_LINK('%s: undefined NULL value reference: %s'\
                  % (Obj.get_fullname(), text)))
        elif GLOBAL.VALUE[ref]['type'] != TYPE_NULL:
            raise(ASN1_PROC_TEXT('%s: NULL value reference to bad type: %s'\
                  % (Obj.get_fullname(), text)))
        Obj['val'] = GLOBAL.VALUE[ref]['val']
    else:
        Obj['val'] = None
    #
    return text[m.end():].strip()

def parse_value_bool(Obj, text=''):
    # test BOOLEAN ::= TRUE | FALSE
    m = re.match('TRUE|FALSE', text)
    if not m:
        # so this must be a global identifier reference
        m = SYNT_RE_IDENT.match(text)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid BOOLEAN value: %s'\
                  % (Obj['name'], text)))
        ref = m.group()
        if ref not in GLOBAL.VALUE:
            raise(ASN1_PROC_LINK('%s: undefined BOOLEAN value reference: %s'\
                  % (Obj.get_fullname(), text)))
        elif GLOBAL.VALUE[ref]['type'] != TYPE_BOOL:
            raise(ASN1_PROC_TEXT('%s: BOOLEAN value reference to bad type: %s'\
                  % (Obj.get_fullname(), text)))
        Obj['val'] = GLOBAL.VALUE[ref]['val']
    else:
        Obj['val'] = {'TRUE':True, 'FALSE':False}[m.group()]
    #
    return text[m.end():].strip()

def parse_value_integer(Obj, text=''):
    # positive, null or negative integer
    # test INTEGER ::= -10 | 0 | 100
    m = re.match('(?:\-{0,1}0{1})|(?:\-{0,1}[1-9]{1}[0-9]{0,})(?:$|\s{1})', text)
    if not m:
        # so this must be a local or global identifier reference
        m = SYNT_RE_IDENT.match(text)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid INTEGER value: %s'\
                  % (Obj.get_fullname(), text)))
        ref = m.group()
        if Obj['cont'] and ref in Obj['cont']:
            # local
            Obj['val'] = Obj['cont'][ref]
        elif ref in GLOBAL.VALUE:
            # global
            if GLOBAL.VALUE[ref]['type'] == TYPE_INTEGER:
                Obj['val'] = GLOBAL.VALUE[ref]['val']
            else:
                raise(ASN1_PROC_TEXT('%s: INTEGER value reference to bad '\
                      'type: %s' % (Obj.get_fullname(), text)))
        else:
            raise(ASN1_PROC_LINK('%s: undefined INTEGER value reference: %s'\
                  % (Obj.get_fullname(), text)))
    else:
        Obj['val'] = int(m.group())
    #
    return text[m.end():].strip()

def parse_value_enum(Obj, text=''):
    # test ENUMERATED { aBc, bCd, cDe } ::= bCd
    m = SYNT_RE_IDENT.match(text)
    if not m:
        raise(ASN1_PROC_TEXT('%s: invalid ENUMERATED value: %s'\
              % (Obj.get_fullname(), text)))
    val = m.group()
    # check against local identifiers
    if val in Obj['cont']:
        Obj['val'] = val
    # 2) or maybe it's a global reference (unlikely, but who knows...)
    elif val in GLOBAL.VALUE:
        if GLOBAL_VALUE[val]['type'] == TYPE_ENUM:
            val = GLOBAL.VALUE[val]['val']
            # afterall, this must correspond to a local identifier
            if val in Obj['cont']:
                Obj['val'] = val
            else:
                raise(ASN1_PROC_TEXT('%s: ENUMERATED value reference '\
                      'mismatch: %s' % (Obj.get_fullname(), text)))
        else:
            raise(ASN1_PROC_TEXT('%s: ENUMERATED value reference to bad '\
                  'type: %s' % (Obj.get_fullname(), text)))
    else:
        raise(ASN1_PROC_LINK('%s: undefined ENUMERATED value reference: %s'\
              % (Obj.get_fullname(), text)))
    #
    return text[m.end():].strip()

def parse_value_bitstr(Obj, text=''):
    # test B-STRING ::= '1100110010110010'B
    # test H-STRING ::= '0123456789abcdef'H
    text = text.strip()
    # check for bstring
    m = re.match('\'[\s01]{0,}\'B', text)
    if not m:
        # check for hstring
        m = re.match('\'[\s0-9A-F]{0,}\'H', text)
        if not m:
            # check for local or global reference
            m = SYNT_RE_IDENT.match(text)
            if not m:
                # check for named bit string
                return _parse_value_named_bitstr(Obj, text)
            ref = m.group()
            if ref not in GLOBAL.VALUE:
                raise(ASN1_PROC_LINK('%s: undefined BIT STRING value '\
                      'reference: %s' % (Obj.get_fullname(), text)))
            elif GLOBAL.VALUE[ref]['type'] != TYPE_BIT_STR:
                raise(ASN1_PROC_TEXT('%s: BIT STRING value reference to '\
                      'bad type: %s' % (Obj.get_fullname(), text)))
            Obj['val'] = GLOBAL.VALUE[m.group()]['val']
        else:
            # hstring
            Obj['val'] = convert_hstr(m.group())
    else:
        # bstring
        Obj['val'] = convert_bstr(m.group())
    #
    return text[m.end():].strip()

def _parse_value_named_bitstr(Obj, text):
    # test BIT STRING {b1(0), b2(1), b3(2)} ::= {b1, b3}
    text, text_nb = extract_curlybrack(text)
    if text_nb is None:
        raise(ASN1_PROC_TEXT('%s: invalid BIT STRING value: %s'\
              % (Obj.get_fullname(), text)))
    nbs = map(stripper, text_nb.split(','))
    names = []
    for nb in nbs:
        m = SYNT_RE_IDENT.match(nb)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid BIT STRING named bit: %s'\
                  % (Obj.get_fullname(), nb)))
        elif SYNT_RE_REMAINING.search(nb[m.end():]):
            raise(ASN1_PROC_TEXT('%s: invalid BIT STRING named bit: %s'\
                  % (Obj.get_fullname(), nb)))
        names.append( m.group() )
    #
    # convert names to (integral value, bit length)
    # get the highest named bit position to determine a bit length
    highest = max(Obj['cont'].values())
    val = 0
    for nb in names:
        if nb not in Obj['cont']:
            raise(ASN1_PROC_TEXT('%s: invalid BIT STRING named bit: %s'\
                  % (Obj['name'], nb)))
        val += 1 << (highest - Obj['cont'][nb])
    Obj['val'] = (val, highest+1)
    #
    return text

def parse_value_str(Obj, text=''):
    # test B-STRING ::= '1100110010110010'B, left-padded
    # test H-STRING ::= '0123456789abcdef'H, left-padded
    text = text.strip()
    # check for bstring
    m = re.match('\'([\s01]{0,})\'B', text)
    if not m:
        # check for hstring
        m = re.match('\'([\s0-9A-F]{0,})\'H', text)
        if not m:
            # check for global identifier
            m = SYNT_RE_IDENT.match(text)
            if not m:
                raise(ASN1_PROC_TEXT('%s: invalid OCTET STRING value: %s'\
                      % (Obj['name'], text)))
            ref = m.group()
            if ref not in GLOBAL.VALUE:
                raise(ASN1_PROC_LINK('%s: undefined OCTET STRING value '\
                      'reference: %s' % (Obj.get_fullname(), text)))
            if GLOBAL.VALUE[ref]['type'] not in (TYPE_OCTET_STR, TYPE_IA5_STR, 
            TYPE_PRINT_STR):
                raise(ASN1_PROC_TEXT('%s: OCTET STRING value reference to '\
                      'bad type: %s' % (Obj.get_fullname(), text)))
            Obj['val'] = GLOBAL.VALUE[ref]['val']
        else:
            # hstring
            h = m.group(1)
            if len(h) % 2 != 0:
                h += '0'
            Obj['val'] = h.decode('hex')
    else:
        # bstring
        b = m.group(1)
        pad_len = len(b) % 8
        if  pad_len != 0:
            b += (8-pad_len) * '0'
        Obj['val'] = ''.join(map(chr, map(lambda x:int(x,2), 
                                 [b[i:i+8] for i in range(0, len(b), 8)])))
    #
    return text[m.end():].strip()

def parse_value_oid(Obj, text=''):
    # id-dsa OBJECT IDENTIFIER ::= { iso(1) member-body(2) us(840) x9-57(10040) 
    #                                x9algorithm(4) 1 }
    text, text_oid = extract_curlybrack(text)
    if text_oid is None:
        # so this must be a global identifier
        m = SYNT_RE_IDENT.match(text)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid OID value: %s'\
                  % (Obj['name'], text)))
        ref = m.group()
        if ref not in GLOBAL.VALUE:
            raise(ASN1_PROC_LINK('%s: undefined OID value reference: %s'\
                  % (Obj.get_fullname(), text)))
        elif GLOBAL.VALUE[ref]['type'] != TYPE_OID:
            raise(ASN1_PROC_LINK('%s: OID value reference to bad type: %s'\
                  % (Obj.get_fullname(), text)))
        Obj['val'] = GLOBAL.VALUE[ref]['val']
        return text[m.end():].strip()
    #
    val = []
    m = SYNT_RE_OID_COMP.match(text_oid)
    while m:
        if m.group(1):
            # NumberForm
            val.append(int(m.group(1)))
        elif m.group(4):
            # NameAndNumberForm
            val.append(int(m.group(4)))
        elif m.group(3):
            # NameForm
            if m.group(3) in ASN1_OID_ISO:
                val.append(int(ASN1_OID_IDO[m.group(3)]))
            else:
                raise(ASN1_PROC_NOSUPP('%s: unknown named OID component: %s'\
                      % (Obj['name'], m.group(3))))
        text_oid = text_oid[m.end():].strip()
        m = SYNT_RE_OID_COMP.match(text_oid)
    #
    if SYNT_RE_REMAINING.match(text_oid):
        raise(ASN1_PROC_TEXT('%s: remaining invalid OID syntax: %s'\
              % (Obj.get_fullname(), text_oid)))
    Obj['val'] = val
    #
    return text

def parse_value_choice(Obj, text=''):
    raise(ASN1_PROC_NOSUPP)

def parse_value_seq(Obj, text=''):
    raise(ASN1_PROC_NOSUPP)

def parse_value_set(Obj, text=''):
    raise(ASN1_PROC_NOSUPP)

def parse_value_seq_of(Obj, text=''):
    raise(ASN1_PROC_NOSUPP)

def parse_value_set_of(Obj, text=''):
    raise(ASN1_PROC_NOSUPP)

def parse_value_class(Obj, text=''):
    # { ID id-MME-UE-S1AP-ID CRITICALITY reject TYPE MME-UE-S1AP-ID 
    #   PRESENCE mandatory}
    text, text_val = extract_curlybrack(text)
    if text_val is None:
        # so this must be a global identifier reference
        m = SYNT_RE_IDENT.match(text)
        if not m:
            raise(ASN1_PROC_TEXT('%s: invalid CLASS content: %s'\
                  % (Obj['name'], text)))
        ref = m.group()
        if ref not in GLOBAL.VALUE:
            raise(ASN1_PROC_LINK('%s: undefined CLASS value reference: %s'\
                  % (Obj.get_fullname(), text)))
        elif GLOBAL.VALUE[ref]['type'] != TYPE_CLASS:
            raise(ASN1_PROC_TEXT('%s: CLASS value reference to bad type: %s'\
                  % (Obj.get_fullname(), text)))
        Obj['val'] = GLOBAL.VALUE[ref]['val']
        return text[m.end():].strip()
    #
    # collect all values passed to each field
    if Obj['syntax'] is not None:
        text_val = _parse_value_class_by_syntax(Obj, text_val)
    else:
        text_val = _parse_value_class_by_ident(Obj, text_val)
    # enforce all values according to each field's type
    _parse_value_class_type_enforce(Obj)
    #
    if SYNT_RE_REMAINING.search(text_val):
        raise(ASN1_PROC_TEXT('%s: CLASS value remaining text: %s'\
              % (Obj.get_fullname(), text_val)))
    #
    return text

def _parse_value_class_by_syntax(Obj, text=''):
    #
    idents, ident_index, offsets = Obj['syntax'].keys(), 0, []
    val = OD()
    #
    while ident_index < len(idents):
        ident = idents[ident_index]
        m = re.search(ident, text)
        if not m:
            group_num = Obj['syntax'][ident][1]
            if group_num is not None:
                # optional SYNTAX ident missing
                # drop all SYNTAX idents in the same optional group
                while Obj['syntax'][ident][1] == group_num:
                    ident_index += 1
                    ident = idents[ident_index]
            else:
                # mandatory SYNTAX ident missing
                raise(ASN1_PROC_TEXT('%s: CLASS value missing mandatory '\
                      'SYNTAX %s: %s' % (Obj.get_fullname(), ident, text)))
        else:
            # can provide the value assignment to previous SYNTAX ident
            if len(val) > 0:
                val[val.keys()[-1]] = text[:m.start()].strip()
            # SYNTAX ident value initialized
            val[Obj['syntax'][m.group()][0]] = None
            text = text[m.end():]
            ident_index += 1
    if len(val) > 0:
        # provide the value assignment to last SYNTAX ident
        val[val.keys()[-1]] = text.strip()
    #
    Obj['val'] = val
    return ''

def _parse_value_class_by_ident(Obj, text=''):
    #
    idents, ident_index, offsets = Obj['cont'].keys(), 0, []
    val = OD()
    #
    while ident_index < len(idents):
        ident = idents[ident_index]
        m = re.search(ident, text)
        if not m:
            if Obj['cont'][ident]['opt'] is not None \
            or Obj['cont'][ident]['def'] is not None:
                # optional ident missing
                ident_index += 1
            else:
                # mandatory ident missing
                raise(ASN1_PROC_TEXT('%s: CLASS value missing mandatory '\
                      'ident %s: %s' % (Obj.get_fullname(), ident, text)))
        else:
            # can provide the value assignment to previous identifier
            if len(val) > 1:
                val[val.keys()[-1]] = text[:m.start()].strip()
            # ident value provided
            val[m.group()] = None
            text = text[m.end():]
            ident_index += 1
    if len(val) > 0:
        # provide the value assignment to last identifier
        val[val.keys()[-1]] = text.strip()
    #
    Obj['val'] = val
    return ''

def _parse_value_class_type_enforce(Obj):
    for ident in Obj['val']:
        val_str = Obj['val'][ident]
        if Obj['cont'][ident]['type'] in (TYPE_OPEN, TYPE_ANY):
            # global reference to the subtype
            if val_str not in GLOBAL.TYPE:
                raise(ASN1_PROC_LINK('%s: undefined CLASS open type: %s'\
                      % (Obj.get_fullname(), val_str)))
            Obj['val'][ident] = GLOBAL.TYPE[val_str]
        else:
            # use the CLASS field to parse the value according to its type
            field = Obj['cont'][ident]
            assert( field['val'] is None )
            assert( field['mode'] in (0, 1))
            rest = parse_value(field, val_str)
            if rest:
                raise(ASN1_PROC_TEXT('%s: CLASS value remaining text: %s'\
                      % (Obj.get_fullname(), val_str)))
            Obj['val'][ident] = field['val']
            field['val'] = None

#------------------------------------------------------------------------------#
# ASN.1 set parser
#------------------------------------------------------------------------------#
# a set is in curly brackets: { ... }
# all root or extended values are separated with |: { a | b | c, ..., e | f }
# the extension mark is: , ...,

def parse_set(Obj, text=''):
    '''
    parses any set assigned to an ASN.1 type or class
    
    set a dict {'root': list of values, 'ext': list of values or None} in Obj['val'],
        each list containing ASN.1 values corresponding to the Obj type
    
    returns the rest of the text
    '''
    text, text_set = extract_curlybrack(text)
    if text_set is None:
        raise(ASN1_PROC_TEXT('%s: invalid set: %s'\
              % (Obj.get_fullname(), text)))
    #
    # check coma for extension marker
    coma_offsets = [-1] + search_top_lvl_sep(text_set, ',') + [len(text_set)]
    sets = map(stripper, [text_set[coma_offsets[i]+1:coma_offsets[i+1]] \
                          for i in range(len(coma_offsets)-1)])
    #
    Root, Ext = [], None
    if len(sets) == 1:
        # rootSet or "..."
        if sets[0] == '...':
            Ext = []
        else:
            Root = parse_set_elements(Obj, sets[0])
    elif len(sets) == 2:
        # rootSet + "..." or "..." + extSet
        if sets[0] == '...':
            Ext = parse_set_elements(Obj, sets[1])
        elif sets[1] == '...':
            Ext = []
            Root = parse_set_elements(Obj, sets[0])
        else:
            raise(ASN1_PROC_TEXT('%s: invalid set: %s'\
                  % (Obj.get_fullname(), text_set)))
    elif len(sets) == 3:
        # rootSet + "..." + extSet
        if sets[1] != '...':
            raise(ASN1_PROC_TEXT('%s: invalid set: %s'\
                  % (Obj.get_fullname(), text_set)))
        else:
            Root = parse_set_elements(Obj, sets[0])
            Ext = parse_set_elements(Obj, sets[2])
    else:
        raise(ASN1_PROC_TEXT('%s: invalid set: %s'\
              % (Obj.get_fullname(), text_set)))
    #
    Obj['val'] = {'root':Root, 'ext':Ext}
    return text
    
def parse_set_elements(Obj, text=''):
    # check for | marker
    or_offsets = [-1] + search_top_lvl_sep(text, '|') + [len(text)]
    elts = map(stripper, [text[or_offsets[i]+1:or_offsets[i+1]] \
                          for i in range(len(or_offsets)-1)])
    #
    val = []
    for elt in elts:
        # 1) check if the element references another set
        m = SYNT_RE_SET_ELT.match(elt)
        if m:
            if m.group(1):
                elt = m.group(1)
                if elt not in GLOBAL.SET:
                    raise(ASN1_PROC_LINK('%s: undefined set reference: %s'\
                          % (Obj.get_fullname(), elt)))
                elif GLOBAL.SET[elt]['type'] != Obj['type']:
                    raise(ASN1_PROC_TEXT('%s: set reference to bad type: %s'\
                          % (Obj.get_fullname(), elt)))
                if GLOBAL.SET[elt]['val']['root'] is not None:
                    val.extend(GLOBAL.SET[elt]['val']['root'])
                if GLOBAL.SET[elt]['val']['ext'] is not None:
                    val.extend(GLOBAL.SET[elt]['val']['ext'])
            # 2) check if the element references a value
            elif m.group(2):
                elt = m.group(2)
                if elt not in GLOBAL.VALUE:
                    raise(ASN1_PROC_LINK('%s: undefined value reference: %s'\
                          % (Obj.get_fullname(), elt)))
                elif GLOBAL.VALUE[elt]['type'] != Obj['type']:
                    raise(ASN1_PROC_TEXT('%s: value reference to bad type: %s'\
                          % (Obj.get_fullname(), elt)))
                val.append(GLOBAL.VALUE[elt]['val'])
        # 3) check if the element is a value
        # let it raise in case there is something wrong
        else:
            assert( Obj['val'] is None )
            assert( Obj['mode'] == 2)
            Obj['mode'] = 1
            rest = parse_value(Obj, elt)
            val.append( Obj['val'] )
            Obj['val'] = None
            Obj['mode'] = 2
            if SYNT_RE_REMAINING.search(rest):
                raise(ASN1_PROC_TEXT('%s: remaining value syntax definition: %s'\
                      % (Obj.get_fullname(), rest)))
    return val

#------------------------------------------------------------------------------#
# ASN.1 constraint parser
#------------------------------------------------------------------------------#
# WARNING: the only constraints supported are:
# - INTEGER:
#   -> single value
#   -> value range, extensions are not handled properly (only True / False)
# - BIT STRING / OCTET STRING / IA5String / PrintableString / SEQUENCE OF / SET OF: 
#   -> SIZE constraint is handled like the INTEGER one
# - BIT STRING / OCTET STRING
#   -> CONTAINING constraint keeps track of the reference name
# - CLASS field
#   -> type inclusion referring to object information set, 
#      constraint keeps track of the references' names

def parse_constraint_integer(Obj, text=''):
    '''
    parses INTEGER constraint in "(" ")"
    
    appends a dict of constraint parameters ('text', 'type', 'keys', various)
    in Obj['const']
    
    returns the rest of the text
    '''
    text, text_const = extract_parenth(text)
    if not text_const:
        return text
    #
    m = SYNT_RE_VAL_RANGE.match(text_const)
    if not m:
        # 1) parse single value constraint
        m = SYNT_RE_SINGLE_VAL.match(text_const)
        if not m:
            raise(ASN1_PROC_NOSUPP('%s: INTEGER constraint not supported: %s'\
                  % (Obj.get_fullname(), text_const)))
        Const = {'text':text_const, 
                 'type':CONST_SINGLE_VAL,
                 'keys':('val', 'ext')}
        if m.group(2) is not None:
            Const['val'] = _resolve_int_ref(Obj, m.group(2), 
                                referrer=['const', len(Obj['const']), 'val'])
        else:
            Const['val'] = int(m.group(1))
        text_const = text_const[m.end():].strip()
    else:
        # 2) parse value range constraint
        Const = {'text':text_const,
                 'type':CONST_VAL_RANGE, 
                 'keys':('lb', 'ub', 'ext')}
        if m.group(2) is not None:
            Const['lb'] = int(m.group(2))
        elif m.group(3) is not None:
            Const['lb'] = _resolve_int_ref(Obj, m.group(3),
                                referrer=['const', len(Obj['const']), 'lb'])
        elif m.group(4) is not None:
            # MIN
            Const['lb'] = None
        if m.group(7) is not None:
            Const['ub'] = int(m.group(7))
        elif m.group(8) is not None:
            Const['ub'] = _resolve_int_ref(Obj, m.group(8),
                                referrer=['const', len(Obj['const']), 'ub'])
        elif m.group(9) is not None:
            # MAX
            Const['ub'] = None
        text_const = text_const[m.end():].strip()
    #
    # 3) parse extension (True / False only)
    # TODO: full INTEGER extension parsing (the recursive way)
    if re.match(',\s{0,}\.{3}', text_const):
        Const['ext'] = True
    else:
        Const['ext'] = False
    #
    if Obj._const:
        for c in Obj._const:
            if c['type'] == CONST_SINGLE_VAL \
            or c['type'] == CONST_VAL_RANGE:
                raise(ASN1_PROC_NOSUPP('%s: multiple integer constraints'))
    
    Obj['const'].append(Const)
    #
    text_more, text_const = extract_parenth(text)
    if text_const:
        raise(ASN1_PROC_NOSUPP('%s: more than 1 constraint: %s'\
              % (Obj.get_fullname(), text_const)))
    return text

def _resolve_int_ref(Obj, val_ref='', referrer=[]):
    #
    Obj_param = Obj.get_param()
    #
    # 1) if Obj is INTEGER, check against local content
    if Obj['type'] == TYPE_INTEGER \
    and Obj['cont'] and val_ref in Obj['cont']:
        return Obj['cont'][val_ref]
    #
    # 2) check against local parameters
    elif Obj_param and val_ref in Obj_param:
        # this requires late resolution (after parameter gets a value,
        # when parsing subtype content)
        Obj_param[val_ref]['ref'].append((Obj.get_parent_path()+referrer, False))
        return None
    #
    # 3) check against global scope
    elif val_ref in GLOBAL.VALUE:
        if GLOBAL.VALUE[val_ref]['type'] != TYPE_INTEGER:
            raise(ASN1_PROC_TEXT('%s: INTEGER constraint reference to bad type: %s'\
                  % (Obj.get_fullname(), val_ref)))
        return GLOBAL.VALUE[val_ref]['val']
    #
    raise(ASN1_PROC_LINK('%s: undefined INTEGER constraint reference: %s'\
          % (Obj.get_fullname(), val_ref)))

def parse_constraint_size(Obj, text=''):
    '''
    parses SIZE constraint in "(" ")"
    
    appends a dict of constraint parameters ('text', 'type', 'keys', various)
    in Obj['const']
    
    returns the rest of the text
    '''
    text, text_const = extract_parenth(text)
    if not text_const:
        return text
    #
    m = re.match('SIZE', text_const)
    if not m:
        return text
    #
    text_const = text_const[m.end():].strip()
    text_const = parse_constraint_integer(Obj, text_const)
    if text_const:
        raise(ASN1_PROC_TEXT('%s: invalid SIZE constraint: %s'\
              % (Obj.get_fullname(), text_const)))
    #
    text_more, text_const = extract_parenth(text)
    if text_const:
        raise(ASN1_PROC_NOSUPP('%s: more than 1 constraint: %s'\
              % (Obj.get_fullname(), text_const)))
    return text

def parse_constraint_str(Obj, text=''):
    '''
    parses constraint in "(" ")" related to string object
    
    appends a dict of constraint parameters ('text', 'type', 'keys', various)
    in Obj['const']
    
    returns the rest of the text
    '''
    # SIZE constraint, CONTAINING constraint
    text_rest, text_const = extract_parenth(text)
    if not text_const:
        return text
    #
    # 1) check for SIZE constraint
    if re.match('SIZE', text_const):
        return parse_constraint_size(Obj, text)
    #
    # 2) check for CONTAINING constraint
    if Obj['type'] in (TYPE_BIT_STR, TYPE_OCTET_STR):
        m = SYNT_RE_CONTAINING.match(text_const)
        if not m:
            raise(ASN1_PROC_NOSUPP('%s: STRING constraint not supported: %s'\
                  % (Obj.get_fullname(), text_const)))
        Const = {'text':text_const,
                 'type':CONST_CONTAINING,
                 'keys':['ref']}
        ref = m.group(1)
        if ref not in GLOBAL.TYPE:
            raise(ASN1_PROC_LINK('%s: undefined CONTAINING type: %s'\
                  % (Obj.get_fullname(), text_const)))
        Const['ref'] = GLOBAL.TYPE[ref]
        Obj['const'].append(Const)
    #
    text_more, text_const = extract_parenth(text_rest)
    if text_const:
        raise(ASN1_PROC_NOSUPP('%s: more than 1 constraint: %s'\
              % (Obj.get_fullname(), text_const)))
    return text_rest

def parse_constraint_clafield(Obj, text=''):
    '''
    parses constraint in "(" ")" related to CLASS fields within ASN.1 types
    
    appends a dict of constraint parameters ('text', 'type', 'keys', various)
    in Obj['const']
    
    returns the rest of the text
    '''
    # this corresponds to CLASS fields used within ASN.1 types, 
    # constrained by object info sets
    text, text_const = extract_parenth(text)
    if not text_const:
        return text
    #
    m = SYNT_RE_SET_REF.match(text_const)
    if not m:
        raise(ASN1_PROC_NOSUPP('%s: CLASS field constraint not supported: %s'\
                  % (Obj.get_fullname(), text_const)))
    Const = {'text':text_const,
             'type':CONST_SET_REF,
             'keys':['ref', 'at'],
             'ref': _resolve_set_ref(Obj, m.group(1), 
                        referrer=['const', len(Obj['const']), 'ref'])}
    if m.group(2) is not None:
        Const['at'] = m.group(2)
        # TODO: check that this refers to a UNIQUE field of the 'ref' ASN1Obj
    else:
        Const['at'] = None
    #
    Obj['const'].append(Const)
    #
    text_more, text_const = extract_parenth(text)
    if text_const:
        raise(ASN1_PROC_NOSUPP('%s: more than 1 constraint: %s'\
              % (Obj.get_fullname(), text_const)))
    return text

def _resolve_set_ref(Obj, ref='', referrer=[]):
    #
    Obj_param = Obj.get_param()
    #
    # 1) check against local parameters
    if Obj_param and ref in Obj_param:
        Obj_param[ref]['ref'].append((Obj.get_parent_path()+referrer, True))
        return None
    #
    # 2) check against global scope
    elif ref[0].isupper() and ref in GLOBAL.SET:
        if GLOBAL.SET[ref]['type'] != TYPE_CLASS:
            raise(ASN1_PROC_TEXT('%s: CLASS field constraint reference to bad '\
                  'type: %s' % (Obj.get_fullname(), ref)))
        return GLOBAL.SET[ref]
    #
    elif ref[0].islower() and ref in GLOBAL.VALUE:
        if GLOBAL.VALUE[ref]['type'] != TYPE_CLASS:
            raise(ASN1_PROC_TEXT('%s: CLASS field constraint reference to bad '\
                  'type: %s' % (Obj.get_fullname(), ref)))
        return GLOBAL.VALUE[ref]
    #
    raise(ASN1_PROC_LINK('%s: undefined CLASS field constraint reference: %s'\
          % (Obj.get_fullname(), ref)))
