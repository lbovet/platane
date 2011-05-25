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
import optparse
import scheduler
import visualize
from Cheetah.Template import Template

# constants for resolution and period
day=0
week=1
month=2

list_template = Template.compile(file=file('list.html', "r"))
task_template = Template.compile(file=file('task.html', "r"))

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
        if d and d['type'] == 'render':
            content, mime = eval(d['function']+'(path, env)')
            start_response('200 OK', [('Content-Type', mime), ('Content-Length', str(len(content)))])        
            return content
        if not m:
            m = model.load(path)
        content, redirect = handler(path, d, m, env)
        if redirect:
            redirect = model.normalize(redirect)
            close=''
            qs = urlparse.parse_qs(env['QUERY_STRING'])
            if 'c' in qs:
                if qs['c'][0]=='0':
                    close='?c=1'
                if qs['c'][0]=='1':
                    close='?c=2'
            start_response('302 Redirect', [('Location', redirect+"/"+close)])            
            return
        else:
            start_response('200 OK', [('Content-Type', 'text/html'), ('Content-Length', str(len(content)))])        
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
    return scheduler.render(tasks, { 'path': path, 'qs' : {}, 'context' : '/', 'sum': False, 'add': model.parent(path)+'/tasks' }), 'text/html'
    
def show_unit_tasks(path, env):
    schedules_by_date = {}
    people = model.parent(path)+'/people'
    min_date = datetime.date.today() + datetime.timedelta(days=90)
    max_date = datetime.date.today()
    n=0
    for person in model.load(people):
        tasks = []
        model.traverse( people+'/'+person, lambda p : tasks.append(p[1]) )
        dates, slots, sched = scheduler.prepare_schedule(tasks, resolution=day)
        if dates[0] < min_date:
            min_date = dates[0]
        if dates[-1] > max_date:
            max_date = dates[-1]
        if dates[0] in schedules_by_date:
            l = schedules_by_date[dates[0]]
        else:
            l = []
            schedules_by_date[dates[0]] = l
        l.append([ person, slots, sum(slots), sum(slots), {'url': people+'/'+person+'/planning' } ])
        n+=1.0
    dates = [ d for d in scheduler.calendar(from_date=min_date, to_date=max_date) ]
    slots = [0]*len(dates)
    #Align and add missing slots
    i=0
    for d in dates:
        if d in schedules_by_date:
            for s in schedules_by_date[d]:
                # fill before and after existing slots
                s[1] = ([0]*i) + s[1]
                if len(s[1]) < len(slots):
                    s[1] = s[1] + ([0]*(len(slots)-len(s[1])))
                for j in range(len(slots)):
                    slots[j] = slots[j] + s[1][j] / n
        i+=1
    s = []
    for i in schedules_by_date.values():
        s.extend(i)

    return visualize.render(dates, slots, sorted(s), vars={'qs':{}, 'context':'/', 'path':path, 'sum':True }), "text/html"


routes = [
    (r'GET /(?P<path>.*)', do_get),    
    (r'PUT /(?P<path>.*)', do_put),   
    (r'POST /(?P<path>.*)', do_post),   
    (r'DELETE /(?P<path>.*)', do_delete),   
]        
    
application = restlite.router(routes)
    
if __name__ == '__main__':
    import sys
    from wsgiref.simple_server import make_server    
    opt_parser=optparse.OptionParser()    
    opt_parser.add_option("-r", "--root", dest="root",
                      help="Root for data", metavar="ROOT")
    opt_parser.add_option("-p", "--port", dest="port",
                      help="Listen port (defaults to 7780)", metavar="PORT")
    opt_parser.add_option("-d", action="store_true", dest="debug", help="Logs debug information on the console")
    (options, args) = opt_parser.parse_args()    
    if options.root:
        model.root = options.root
    if options.debug:
        restlite._debug = True
    if options.port:
        port = int(options.port)
    else:
        port = 7780        
    httpd = make_server('', port, application)    
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass