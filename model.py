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

# interface 

''''
Returns the expected type for this path:
A dictionary containing:
- A 'type' being 'dict', 'list', 'leaf'
- An 'attributes' dictionary (for all types)
- A 'children' list containing child names (for dict and list types)
Returns None if path does not match the schema
'''
def describe(path):
    element = schema['root']
    path='root'+path
    attributes = None
    children = None
    type = None

    for name in path.split('/'):                
        if len(name.strip()) == 0:
            continue        
        if children and name in children:
            element = element[name]
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
    return result
    
'''
Creates a path. 
Idempotent, will not fail if the path already exist.
'''
def create(path):
    path = normalize(path)
    d = describe(path)
    if d:
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
            result = load_internal(path, d)        
        if d['type'] == 'leaf':
            result = check_attributes(result, d['attributes'])
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
        attributes = check_attributes(attributes, d['attributes'])
        save_internal(path, attributes, d)
    else:
        raise NotFoundException('Invalid path or non-leaf path: '+path)

'''
Delete a path.
'''
def delete(path):
    path = normalize(path)
    d = describe(path)
    if d and describe('/'.join(path.split('/')[:-1]))['type'] == 'list':
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
        path.replace('//', '/')
    if len(path) > 0 and path[-1] == '/':
        path = path[:-1]
    if len(path) == 0:
        path = '/'        
    if path[0] != '/':
        path = '/' + path        
    return path

def check_attributes(attr_dict, attr_schema):
    # TODO: implement validation, default values...
    return attr_dict

def as_dict(element):
    if element.has_key('dict'):
        return element['dict']

def as_list(element):
    if element.has_key('list'):
        return element['list']
    
def get_attributes(element):
    if element.has_key('attributes'):
        return element['attributes']
        
# filesystem implementation

root = 'data'
schema = yaml.load( file(root+'/schema', 'r'))

import os, os.path

def create_internal(path, d):
    if not os.path.exists(root+path):
        if d['type'] == 'leaf':
            if not os.path.exists(root+'/'.join(path.split('/')[:-1])):
                os.makedirs(root+'/'.join(path.split('/')[:-1]))
            yaml.dump({}, file(root+path, "w"));
        if d['type'] == 'dict':              
            os.makedirs(root+path)
        if d.has_key('children'):
            for c in d['children']:
                if not os.path.exists(root+path+'/'+c):
                    os.mkdir(root+path+'/'+c)
    
def load_internal(path, d):    
    if os.path.exists(root+path):
        if d['type'] == 'list':
            return os.listdir(root+path)
        if d['type'] == 'leaf':
            return yaml.load(file(root+path))
    else:
        raise NotFoundException('Path not found: '+path)

def save_internal(path, attributes, d):
    if os.path.exists(root+path):
        yaml.dump(attributes, file(root+path, "w"));
    else:
        raise NotFoundException('Path not found: '+path)    

def delete_internal(path):
    pass

# test

if __name__ == '__main__':
    p = '/units/IT121/people/bovetl/tasks/JIRA-23'
    d = '/units/IT121/people/bovetl/tasks/'    
    print describe(p)
    create(p)
    save(p, { 'name': 'JIRA-23' })
    print load(p)
    print load('/')
    print load(d)