#!/usr/bin/python
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

import restlite
import model
import urlparse
import urllib
import datetime
import scheduler
from Cheetah.Template import Template

list_template = Template.compile(file=file('list.html', "r"))
task_template = Template.compile(file=file('task.html', "r"))

restlite._debug = True

def do_get(env, start_response):
    return handle(env, start_response, get_body)
   
def get_body(path, d, m, env):
    parent_type = None
    parent = model.parent(path)
    qs = urlparse.parse_qs(env['QUERY_STRING'])

    if parent:
        parent_type = model.describe(parent)['type']
    if d['type'] == 'leaf':
        for k,v in m.iteritems():
            if v and type(v) == datetime.date:
                m[k]=v.strftime('%d.%m.%Y')
            if type(v) == float and v == int(v):
                m[k] = int(v)            
            if v == 0 or v == 0.0:
                m[k] = ''    
        errors = ()        
        if 'e' in qs:
            errors = qs['e']
            for k in m.keys():
                if k in qs:
                    m[k] = qs[k][0]
        return str(task_template(searchList=[ { 'context': '/', 'path':path, 'parent_type': parent_type, 'attributes': m, 'errors': errors, 'qs': qs } ])), None
    else:
        return str(list_template(searchList=[ { 'context': '/', 'path':path, 'parent_type': parent_type, 'list' : m, 'type':  d['type'], 'qs':qs } ])), None

def do_put(env, start_response):
    return handle(env, start_response, save_body, m=get_post(env))
    
def do_post(env, start_response):
    m = get_data(env)
    if 'method' in m.keys():            
        if m['method'] == 'DELETE':
            return handle(env, start_response, delete_body, m)
    return handle(env, start_response, save_body, m)

def get_data(env):
    p = urlparse.parse_qs(env['wsgi.input'].read(int(env['CONTENT_LENGTH'])))
    for k,v in p.iteritems():
        p[k] = v[0]
    return p

def save_body(path, d, m, env):
    if d['type'] == 'leaf':
        model.create(path)
        model.save(path, m)
        return "\n", model.parent(path)
    if d['type'] == 'list' and 'name' in m:
        new_path = path+"/"+m['name']
        if path.strip() == '':
            return "\n", path
        model.create(new_path)    
        if model.describe(new_path)['type'] == 'leaf':
            model.save(new_path, { 'name': m['name'] })
        return "\n", new_path
    return None, path

def do_delete(env, start_response):
    return handle(env, start_response, delete_body, m=get_post(env))

def delete_body(path, d, m, env):
    parent = model.parent(path)
    if parent and model.describe(parent)['type'] == 'list':
        model.delete(path)
        return "\n", parent
    else:
        raise restlite.Status, '403 Forbidden' 
    
def handle(env, start_response, handler, m=None):
    path = get_path(env)
    if len(path) > 0 and not path[-1] == '/':
        start_response('302 Redirect', [('Location', model.normalize(path)+"/")])            
        return
    path = model.normalize(path)
    try:
        d = model.describe(path)
        if d['type'] == 'render':
            content, mime = eval(d['function']+'(path, env)')
            start_response('200 OK', [('Content-Type', mime)])        
            return content
        if not m:
            m = model.load(path)
        content, redirect = handler(path, d, m, env)
        if redirect:
            redirect = model.normalize(redirect)
            close=''
            qs = urlparse.parse_qs(env['QUERY_STRING'])
            print qs
            if 'c' in qs and qs['c'][0]=='1':
                close='?c=2'
            start_response('302 Redirect', [('Location', redirect+"/"+close)])            
            return
        else:
            start_response('200 OK', [('Content-Type', 'text/html')])        
            return content 
    except model.NotFoundException as e:   
        import traceback
        traceback.print_exc()
        raise restlite.Status, '404 Not Found'    
    except model.ParseException as e:
        d = {}
        d.update( { 'e': e.errors } )
        d.update(e.attributes)
        start_response('302 Redirect', [('Location', model.normalize(path)+"/?"+urllib.urlencode(d, True))])
        return
    
def get_path(env):    
    return env['wsgiorg.routing_args']['path'].split('?')[0]

def show_tasks(path, env):
    tasks = []
    model.traverse( model.parent(path), lambda p : tasks.append(p[1]) )
    return scheduler.render(tasks, { 'path': path, 'qs' : {}, 'context' : '/' } ), 'text/html'

routes = [
    (r'GET /(?P<path>.*)', do_get),    
    (r'PUT /(?P<path>.*)', do_put),   
    (r'POST /(?P<path>.*)', do_post),   
    (r'DELETE /(?P<path>.*)', do_delete),   
]        
    
if __name__ == '__main__':
    import sys
    from wsgiref.simple_server import make_server
    
    httpd = make_server('', 8080, restlite.router(routes))
    
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
