##  Copyright 2011 Laurent Bovet <laurent.bovet@windmaster.ch>
##
##  This file is part of Platane.
##
##  Platane is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Lesser General Public License as 
##  published bythe Free Software Foundation, either version 3 of the 
##  License, or (at your option) any later version.
##
##  Platane is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU Lesser General Public License for more details.
##
##  You should have received a copy of the GNU Lesser General Public 
##  License along with Platane. 
##  If not, see <http://www.gnu.org/licenses/>.

import yaml
import datetime
import re

handlers = {}

# interface 

''''
Returns the expected type for this path:
A dictionary containing:
- A 'type' being 'dict', 'list', 'leaf'
- An 'attributes' dictionary (for all types)
- A 'children' list containing child names (for dict and list types)
- A 'render' function name for a special rendering
Returns None if path does not match the schema
'''
def describe(path):
    path = normalize(path)
    element = schema['root']
    path='root'+path
    attributes = None
    children = None
    type = None
    handlers = {}

    for name in path.split('/'):              
        if len(name.strip()) == 0:
            continue                
        if children and name in children:
            element = element[name]        
        handlers.update(get_handlers(element))
        level = as_dict(element)
        if level:
            type = 'dict'
            children = sorted(level.keys())
            attributes = get_attributes(level)
            element = level
            continue
        level = as_list(element)
        if level:
            type = 'list'
            dict_item = as_dict(level)
            if dict_item:
                children = sorted(dict_item.keys())                
            attributes = get_attributes(level)
            if attributes:
                children = None
            element = level
            continue
        level = as_render(element)
        if level:
            return { 'type': 'render', 'function': level['function'] }
        attr = get_attributes(element)
        if attr:
            type='leaf'
            children = None
            attributes = attr
            continue
        return None                        
    result = { 'type': type }
    if attributes:
        result['attributes'] = attributes
    if children:
        result['children'] = children        
    if handlers:
        result['handlers'] = handlers  
    return result
    
'''
Creates a path. 
Idempotent, will not fail if the path already exist.
'''
def create(path):
    path = normalize(path)
    d = describe(path)
    if d:
        if 'handlers' in d:
            if 'create' in d['handlers']:
                handlers[d['handlers']['create']](path)
                return
            else:
                raise Exception("Read only")
        create_internal(path, d)
    else:
        raise NotFoundException('Invalid path '+path)
        
'''
Loads the attributes or items of given path.
'''
def load(path):
    path = normalize(path)
    d = describe(path)   
    if d:
        result = None
        if d['type'] == 'dict':
            return d['children']
        else:
            if 'handlers' in d:
                if 'load' in d['handlers']:
                    result = handlers[d['handlers']['load']](path)
                else:
                    raise Exception("Write only")
            else:
                result = load_internal(path, d)        
        if d['type'] == 'leaf':
            check_attributes(result, d['attributes'])
            result['url'] = path+"/"
        return result
    else:
        raise NotFoundException('Invalid path: '+path)

'''
Save the attributes on an existing path.
'''
def save(path, attributes):
    path = normalize(path)
    d = describe(path)
    if d and d['type'] == 'leaf':
        check_attributes(attributes, d['attributes'])
        if 'handlers' in d:
            if 'save' in d['handlers']:
                handlers[d['handlers']['save']](path, attributes)
            else:
                raise Exception("Read only")
        else:
            save_internal(path, attributes, d)
    else:
        raise NotFoundException('Invalid path or non-leaf path: '+path)

'''
Delete a path.
'''
def delete(path):
    path = normalize(path)
    d = describe(path)
    if d and describe(parent(path))['type'] == 'list':
        if 'handlers' in d:
            if 'delete' in d['handlers']:
                handlers[d['handlers']['delete']](path)
            else:
                raise Exception("Read only")
        else:
            delete_internal(path, d)      
    else:
        raise NotFoundException('Invalid path or not deletable: '+path)

class NotFoundException(Exception):
    pass

# utilities

def normalize(path):
    path = path.strip()
    path = path.replace('..', '')
    while path.find('//') > -1:
        path = path.replace('//', '/')
    if len(path) > 0 and path[-1] == '/':
        path = path[:-1]
    if len(path) == 0:
        path = '/'        
    if path[0] != '/':
        path = '/' + path        
    return path

def parent(path):
    path = normalize(path)
    if len(path) > 0:
        return '/'.join(path.split('/')[:-1])

date_formats = ( (re.compile(r'^([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0]))),
                 (re.compile(r'^([0-9]?[0-9])\.([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0]), month=int(v[1][1]))),
                 (re.compile(r'^([0-9]?[0-9])\.([0-9]?[0-9])\.(20[0-9][0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0]), month=int(v[1][1]), year=int(v[1][2]))),
                 (re.compile(r'^(20[0-9][0-9])-([0-9]?[0-9])-([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][2]), month=int(v[1][1]), year=int(v[1][0]))) )

def traverse(path, function):
    d = describe(path)
    if d['type'] == 'leaf':
        function( (path, load(path), d ) )
    if d['type'] == 'dict' or d['type'] == 'list':
        for child in load(path):
            traverse(path+"/"+child, function)

def check_date(d):
    if type(d) == str:
        if d.strip() == '':
            return None
        r = datetime.date.today()
        for f in date_formats:
            m = f[0].match(d)
            if m:
                return f[1]( (r, m.groups()) )
        raise Exception()
    return d

types = { 'int': [0, int],
             'date': [ None, check_date],
             'str': [ "", str ],
             'float': [ 0.0, float ] }

class ParseException(Exception):
    def __init__(self, attributes, errors):
        self.attributes = attributes
        self.errors = errors

def check_attributes(attr_dict, attr_schema):
    errors = []
    original_attributes = {}
    original_attributes.update(attr_dict)
    for attr in attr_schema.keys():
        try:
            if not attr in attr_dict.keys():
                attr_dict[attr] = types[attr_schema[attr]][0]    
            attr_dict[attr] = types[attr_schema[attr]][1](attr_dict[attr]) # cast to appropriate type
        except:
            errors.append(attr)
    if len(errors)>0:
        raise ParseException(original_attributes, errors)

def as_dict(element):
    if element.has_key('dict'):
        return element['dict']

def as_list(element):
    if element.has_key('list'):
        return element['list']

def as_render(element):
    if element.has_key('render'):
        return element['render']
    
def get_attributes(element):
    if element.has_key('attributes'):
        return element['attributes']
        
def get_handlers(element):
    if element.has_key('handlers'):
        return element['handlers']
    else:
        return {}

# filesystem implementation

data = 'data'
root = data+'/root'
schema = yaml.load( file(data+'/schema', 'r'))

import os, os.path, shutil

def create_internal(path, d):        
    if d['type'] == 'leaf':
        if not os.path.exists(root+parent(path)):
            os.makedirs(root+'/'.join(path.split('/')[:-1]))
        yaml.dump({}, file(root+path, "w"));
    if d['type'] == 'dict':        
        if not os.path.exists(root+path):      
            os.makedirs(root+path)
    if d.has_key('children'):
        for c in d['children']:
            if not os.path.exists(root+path+'/'+c):
                os.mkdir(root+path+'/'+c)
    
def load_internal(path, d):    
    if os.path.exists(root+path):
        if d['type'] == 'list':
            return sorted(os.listdir(root+path))
        if d['type'] == 'leaf':
            return yaml.load(file(root+path))
    else:
        p = parent(path)
        p_d = describe(p)
        if describe(p)['type'] == 'dict':
            create_internal(p, p_d)
            if d['type'] == 'list':
                return sorted(os.listdir(root+path))
            if d['type'] == 'leaf':
                return yaml.load(file(root+path))            
        raise NotFoundException('Path not found: '+path)

def save_internal(path, attributes, d):
    if os.path.exists(root+path):
        yaml.dump(attributes, file(root+path, "w"));
    else:
        raise NotFoundException('Path not found: '+path)    

def delete_internal(path, d):
    if os.path.exists(root+path):
        if d['type'] == 'leaf':
            os.remove(root+path)
        else:
            shutil.rmtree(root+path)

# test

if __name__ == '__main__':    
    p = '/units/IT121/people/bovetl/tasks/JIRA-23'
    d = '/units/IT121/people/bovetl/tasks/'    
    print describe(p)
    create(p)
    save(p, { 'name': 'JIRA-23' })
    save(p, { 'name': 'JIRA-24' })
    print load(p)
    print load('/')
    print load(d)
    t = []
    traverse('/units', lambda(x): t.append(x))
    print t
