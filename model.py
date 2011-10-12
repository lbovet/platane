##  Copyright 2011 Laurent Bovet <laurent.bovet@windmaster.ch>
##
##  This file is part of Platane.
##
##  Platane is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Lesser General Public License as 
##  published by the Free Software Foundation, either version 3 of the 
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

# Provides access to the data hierarchy

import yaml
import datetime
import re
import copy
import urllib
import traceback
import memcache
import os.path, shutil
import logging

handlers = {}
cache = {}
schema = None

log = logging.getLogger("platane.model")

# interface 

''''
Returns the expected type for this path:
A dictionary containing:
- A 'type' being 'dict', 'list', 'leaf'
- An 'attributes' dictionary (for all types)
- A 'children' list containing child names (for dict and list types)
- A 'render' function name for a special rendering
Returns None if path does not match the schema
Awful code. Please refactor :)
'''
def describe(path):
    path = normalize(path)
    element = schema['root']
    path='root'+path
    attributes = None
    children = None
    path_type = None
    handlers = {}
    cache = {}
    for name in path.split('/'):              
        if len(name.strip()) == 0:
            continue                
        if children and name in children:
            element = element[name]        
        handlers.update(get_handlers(element))
        cache = get_cache(element)
        level = as_dict(element)
        if level:
            path_type = 'dict'
            children = sorted(level.keys())
            attributes = get_attributes(level)
            element = level
            continue
        level = as_list(element)
        if level:
            path_type = 'list'
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
            result = { 'type': 'render', 'function': level['function']}
            if 'parameters' in level:
                result['parameters'] = level['parameters']
            if 'cache' in element:
                result['cache'] = element['cache']                           
            return result
        attr = get_attributes(element)
        if attr:
            path_type='leaf'
            children = None
            attributes = attr
            continue
        return None                        
    result = { 'type': path_type }
    if attributes:
        result['attributes'] = attributes
    if children:
        result['children'] = children        
    if handlers:
        result['handlers'] = handlers  
    if cache:
        result['cache'] = cache
    return result
    
'''
Creates a path. 
Idempotent, will not fail if the path already exist.
'''
def create(path):
    path = normalize(path)
    descriptor = describe(path)
    if descriptor:
        if 'handlers' in descriptor:
            if 'create' in descriptor['handlers']:
                handlers[descriptor['handlers']['create']](path)
                return
            else:
                raise Exception("Read only")
        create_internal(path, descriptor)
    else:
        raise NotFoundException('Invalid path '+path)
        
'''
Loads the attributes or items of given path.
'''
def load(path):
    path = normalize(path)
    cached = load_from_cache(path)
    if cached is not None:
        log.debug("Returning cached %s", path)
        return cached
    descriptor = describe(path)   
    if descriptor:
        result = None
        if descriptor['type'] == 'dict':
            return descriptor['children']
        else:
            if 'handlers' in descriptor:
                if 'load' in descriptor['handlers']:
                    load_handler = descriptor['handlers']['load']
                    parameters = {}
                    if 'parameters' in load_handler:
                        parameters = load_handler['parameters']
                    result = handlers[load_handler['function']](path, parameters)
                else:
                    raise Exception("Write only")
            else:
                result = load_internal(path, descriptor)      
        if result == None:
            return None  
        if descriptor['type'] == 'leaf':            
            check_attributes(result, descriptor['attributes'], fix=True)
            result['url'] = path+"/"
        if 'cache' in descriptor:
            log.debug("Caching %s", path)
            put_in_cache(path, copy.copy(result))
        return result
    else:
        raise NotFoundException('Invalid path: '+path)

'''
Save the attributes on an existing path.
'''
def save(path, attributes):
    path = normalize(path)
    descriptor = describe(path)
    if 'cache' in descriptor:
        log.debug("Invalidate cache: %s", path)
        invalidate_cache(path)
    if descriptor and (descriptor['type'] == 'leaf' or descriptor['type'] == 'render'):
        if descriptor['type'] == 'leaf':
            check_attributes(attributes, descriptor['attributes'])
        if 'handlers' in descriptor:
            if 'save' in descriptor['handlers']:
                handlers[descriptor['handlers']['save']](path, attributes)
            else:
                raise Exception("Read only")
        else:
            save_internal(path, attributes, descriptor)
    else:
        raise NotFoundException('Invalid path or non-leaf path: '+path)

'''
Delete a path.
'''
def delete(path):
    path = normalize(path)
    descriptor = describe(path)
    if 'cache' in descriptor:
        log.debug("Invalidate cache: %s", path)
        invalidate_cache(path)   
    if descriptor and descriptor['type'] == 'list':
        for i in load(path):
            delete(path+"/"+i)
        return
    if descriptor and describe(parent(path))['type'] == 'list':
        if 'handlers' in descriptor:
            if 'delete' in descriptor['handlers']:
                handlers[descriptor['handlers']['delete']](path)
            else:
                raise Exception("Read only")
        else:
            delete_internal(path, descriptor)      
    else:
        raise NotFoundException('Invalid path or not deletable: '+path)

'''
Exception raised when searched item was not found.
'''
class NotFoundException(Exception):
    pass

# utilities

'''
Cleans a path into a canonical form.
'''
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

'''
Return the parent path of a given path.
'''
def parent(path):
    path = normalize(path)
    if len(path) > 0:
        return '/'.join(path.split('/')[:-1])

date_formats = ( (re.compile(r'^([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0])), 1),
                 (re.compile(r'^([0-9]?[0-9])\.([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0]), month=int(v[1][1])), 2),
                 (re.compile(r'^([0-9]?[0-9])\.([0-9]?[0-9])\.(20[0-9][0-9])$'), lambda(v) : v[0].replace(day=int(v[1][0]), month=int(v[1][1]), year=int(v[1][2])), 0),
                 (re.compile(r'^(20[0-9][0-9])-([0-9]?[0-9])-([0-9]?[0-9])$'), lambda(v) : v[0].replace(day=int(v[1][2]), month=int(v[1][1]), year=int(v[1][0]))), 0 )

'''
Travers the sub tree of path and call function with one tuple parameter (path, object, descriptor).
Only call function for leaf nodes (tasks), unless all_nodes is True.
'''
def traverse(path, function, all_nodes=False):
    descriptor = describe(path)
    if descriptor['type'] == 'leaf':
        try:
            function( (path, load(path), descriptor ) )
        except ParseException:
            traceback.print_exc() 
    if descriptor['type'] == 'dict' or descriptor['type'] == 'list':   
        node = load(path)           
        if all_nodes:
            try:
                function( (path, node, descriptor ) )
            except ParseException:
                traceback.print_exc()        
        for child in node:
            traverse(path+"/"+child, function, all_nodes)

'''
Check a date string and return the corresponding date. Raise an exception if not parseable.
'''
def check_date(date_or_string):
    today = datetime.date.today()
    if isinstance(date_or_string, basestring):
        if date_or_string.strip() == '':
            return None
        r = datetime.date.today()
        for f in date_formats:
            m = f[0].match(date_or_string)
            if m:                
                new = f[1]( (r, m.groups()) )
                # jump to next month
                if f[2]==1 and new < today:
                    while new < today and new.month<12:
                        new = new.replace(new.year, new.month+1, new.day)
                # jump to next year
                if f[2]>1 and new < today:
                    while new < today:
                        new = new.replace(new.year+1, new.month, new.day)
                return new
        raise Exception()
    return date_or_string
    
'''
Check a string by converting it to unicode if needed.
'''    
def check_string(s):
    if isinstance(s, unicode):
        return s
    else:
        return unicode(s, "utf8")

'''
Maps the declared schema type to a constructor function
'''
types = { 'int': [0, int],
             'date': [ None, check_date],
             'str': [ "", check_string ],
             'float': [ 0.0, float ],
             'bool': [ False, bool ] }

'''
Exception holding parsing information and errors to display 
'''
class ParseException(Exception):
    def __init__(self, attributes, errors):
        self.attributes = attributes
        self.errors = errors

'''
Checks task attributes. Optional fix them to an appropriate default value.
Raises a ParseException if erroneous and fix=False.
'''
def check_attributes(attr_dict, attr_schema, fix=False):
    errors = []
    original_attributes = {}
    original_attributes.update(attr_dict)
    for attr in attr_schema.keys():
        try:
            if not attr in attr_dict.keys():
                attr_dict[attr] = types[attr_schema[attr]][0]    
            attr_dict[attr] = types[attr_schema[attr]][1](attr_dict[attr]) # cast to appropriate type
        except:
            if fix:
                attr_dict[attr] = types[attr_schema[attr]][0] 
            else:
                traceback.print_exc()
                errors.append(attr)            
    if not fix and len(errors)>0:
        raise ParseException(original_attributes, errors)

'''
Check attributes of a path against the schema declaration 
'''
def check(path, attributes):
    descriptor = describe(path)
    if descriptor:
        return check_attributes(attributes, descriptor['attributes'])
    else:
        raise NotFoundException('Invalid path: '+path)

# accessor to sub.elements of the schema.
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

def get_cache(element):
    if element.has_key('cache'):
        return element['cache']
    else:
        return {}

# filesystem implementation of storage functions

data = 'data'
root = data+'/root'

def create_internal(path, descriptor):    
    path = encode(path)
    if descriptor['type'] == 'leaf' or descriptor['type'] == 'render':
        if not os.path.exists(root+parent(path)):
            os.makedirs(root+'/'.join(path.split('/')[:-1]))
        yaml.dump({}, file(root+path, "w"));
    if descriptor['type'] == 'dict':        
        if not os.path.exists(root+path):      
            os.makedirs(root+path)
    if descriptor.has_key('children'):
        for c in descriptor['children']:
            c = decode(c)
            if not os.path.exists(root+path+'/'+c):
                os.mkdir(root+path+'/'+c)
    
def load_internal(path, descriptor):    
    path = encode(path)
    if os.path.exists(root+path):
        if descriptor['type'] == 'list':
            return [ decode(elt) for elt in sorted(os.listdir(root+path)) ]
        if descriptor['type'] == 'leaf':
            return yaml.load(file(root+path, "rb"))
    else:
        p = parent(path)
        p_d = describe(p)
        if describe(p)['type'] == 'dict':
            create_internal(p, p_d)
            if descriptor['type'] == 'list':
                return [ decode(elt) for elt in sorted(os.listdir(root+path)) ]
            if descriptor['type'] == 'leaf':
                return yaml.load(file(root+path))            
        raise NotFoundException('Path not found: '+path)

def save_internal(path, attributes, descriptor):
    path = encode(path)
    if os.path.exists(root+path):
        yaml.dump(attributes, file(root+path, "wb"), allow_unicode=True);
    else:
        raise NotFoundException('Path not found: '+path)    

def delete_internal(path, descriptor):
    path = encode(path)
    if os.path.exists(root+path):
        if descriptor['type'] == 'leaf':
            os.remove(root+path)
        else:
            shutil.rmtree(root+path)

# Url encoding for filesystem names

def encode(s):
    return urllib.quote(s, ' []/' )

def decode(s):
    return urllib.unquote(s)

# Cache interface
    
def load_from_cache(path):
    data = get_from_cache(path)
    if data is not None:
        return copy.deepcopy(data)
    
def invalidate_cache(path, parents=True, children=True):
    p = path    
    while p:
        if p in cache:
            data = get_from_cache(p)
            remove_from_cache(p)                    
        if parents:
            p = parent(p)
        else:
            break
    if children:
        traverse(path, lambda x: remove_from_cache(x[0]), all_nodes=True)

# Cache implementation. Uses memcache if available on localhost.

ext_cache = memcache.Client(['127.0.0.1:11211'], debug=0)

def put_in_cache(path, obj):
    if not ext_cache.set(urllib.quote(path, '/' ), obj):
        log.debug("Putting in local cache: %s", path)
        cache[path] = obj # Cache locally
    
def get_from_cache(path):
    result = ext_cache.get(urllib.quote(path, '/' ))
    if result is not None:
        return result
    if path in cache:
        log.debug("Reading from local cache: %s", path)        
        return cache[path]

def remove_from_cache(path):
    ext_cache.delete(urllib.quote(path, '/' ))
    if path in cache:
        del cache[path]