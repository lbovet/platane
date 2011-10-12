#!/usr/bin/python
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

# Entry point to the Platane application.

import restlite
import model
import urlparse
import urllib
import datetime
import optparse
import copy
import scheduler
import visualize
import jira
import re
import sys, os.path, getpass
import logging
import yaml
from Cheetah.Template import Template
from threading import Thread

# constants for resolution and period
day=0
week=1
month=2

PLATANE_HOME = os.path.dirname(__file__)

model.schema=yaml.load( file(PLATANE_HOME+'/data/schema', 'r'))
model.root=PLATANE_HOME+"/data/root"

list_template = Template.compile(file=file(PLATANE_HOME+'/list.html', "r")  )
task_template = Template.compile(file=file(PLATANE_HOME+'/task.html', "r"))
message_template = Template.compile(file=file(PLATANE_HOME+'/message.html', "r"))
visualize.tasks_template=Template.compile(file=file(PLATANE_HOME+'/tasks.html', "r"))

render_handlers = {}

# REST methods
def do_get(env, start_response):
    return handle(env, start_response, get_body)

def do_put(env, start_response):
    return handle(env, start_response, save_body, m=do_post(env, start_response))
    
def do_post(env, start_response):
    m = get_data(env)
    if 'method' in m.keys():            
        if m['method'] == 'DELETE':
            return handle(env, start_response, delete_body, m)
    return handle(env, start_response, save_body, m)

def do_delete(env, start_response):
    return handle(env, start_response, delete_body, m=do_post(env, start_response))

'''
Main handling of incoming requests. Then dispatches to *_body functions.
'''
def handle(env, start_response, handler, m=None):    
    path = get_path(env)
    if len(path) > 0 and not path[-1] == '/':
        start_response('302 Redirect', [('Location', model.normalize(path)+"/")])            
        return
    path = model.normalize(path)
    try:
        d = model.describe(path)
        qs = urlparse.parse_qs(env['QUERY_STRING'])
        if not m and 'cache' in d:
                if 'r' in qs and qs['r'][0]=='1':
                    if d['cache'] == 'normal':
                        model.invalidate_cache(path)
                    if d['cache'] == 'parent':
                        model.invalidate_cache(model.parent(path))
        if d and d['type'] == 'render' and env['REQUEST_METHOD'] == 'GET':
            parameters = {}
            if 'parameters' in d:
                parameters = d['parameters']
            content, mime = render_handlers[d['function']](path, parameters, env)            
            start_response('200 OK', [('Content-Type', mime), ('Content-Length', str(len(content)))])        
            return content        
        if not m:
            m = model.load(path)
        content, redirect = handler(path, d, m, env)
        if redirect:
            redirect = model.normalize(redirect)
            close=''
            if 'c' in qs:
                if qs['c'][0]=='0':
                    close='?c=1'
                if qs['c'][0]=='1':
                    close='?c=2'
            start_response('302 Redirect', [('Location', redirect+"/"+close)])            
            return
        else:
            start_response('200 OK', [('Content-Type', 'text/html;charset=utf-8'), ('Content-Length', str(len(content)))])        
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

'''
Treats a request to get a task or a list
'''
def get_body(path, d, m, env):
    parent_type = None
    parent = model.parent(path)
    qs = urlparse.parse_qs(env['QUERY_STRING'])
    refreshable = 0
    if parent:
        parent_type = model.describe(parent)['type']
    if 'cache' in d:
        refreshable = 1
    variables = { 'context': '/', 'path':path, 'parent_type': parent_type, 'qs': qs, 'refreshable': refreshable, 'url' : path+"/"}
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
        variables.update({ 'attributes': m, 'errors': errors })
        return str(task_template(searchList=[ variables ])), None
    else:
        variables.update( { 'list' : m, 'type':  d['type'] })
        return str(list_template(searchList=[ variables ])), None

'''
Treats a request to save an object
'''
def save_body(path, d, m, env):
    if d['type'] == 'leaf':
        original=copy.copy(m)
        model.check(path, m)
        errors = []
        if m['to'] and m['from'] and m['to'] < m['from']:
            errors.extend( ('to','from') )
        if (not 'load' in original or original['load'] == '') and (not 'effort' in original or original['effort'] == ''):
            errors.extend( ('load', 'effort') )
        if len(errors) > 0:
            raise model.ParseException(original, errors)
        model.create(path)        
        model.save(path, m)
        return "\n", model.parent(path)
    if d['type'] == 'list' and 'name' in m:
        name = m['name']
        name = name.replace('?', '')
        name = name.replace('/', '')
        name = name.replace('#', '')
        new_path = path+"/"+name
        if path.strip() == '':
            return "\n", path
        model.create(new_path)    
        if model.describe(new_path)['type'] == 'leaf' or model.describe(new_path)['type'] == 'render':
            model.save(new_path, { 'name': m['name'] })
        return "\n", new_path
    return None, path

'''
Treats a request to delete an object
'''
def delete_body(path, d, m, env):
    parent = model.parent(path)
    if parent:
        model.delete(path)
        return "\n", parent
    else:
        raise restlite.Status, '403 Forbidden' 
   
'''
Obtains the object path from the requested url
''' 
def get_path(env):    
    return env['wsgiorg.routing_args']['path'].split('?')[0]

'''
Gets the POST data
'''
def get_data(env):
    p = urlparse.parse_qs(env['wsgi.input'].read(int(env['CONTENT_LENGTH'])))
    for k,v in p.iteritems():
        p[k] = v[0]
    return p

# handlers for planning views

'''
Shows the tasks of a person
'''
def show_tasks(path, parameters, env):
    tasks = []
    model.traverse( model.parent(path), lambda p : tasks.append(p[1]))
    qs = urlparse.parse_qs(env['QUERY_STRING'])
    expand=set()
    if 'x' in qs:
        expand.update(qs['x'])
    return scheduler.render(tasks, { 'path': path, 'qs' : qs, 'context' : '/', 'sum': False, 'add': model.parent(path)+'/tasks/plan/', 'url': path+'/', 'refreshable': True }, 
        resolution=week, expand=expand), 'text/html;charset=utf-8'
render_handlers['show_tasks'] = show_tasks
    
'''
Shows the tasks of a team grouped by person
'''
def show_team_tasks(path, parameters, env):    
    people = model.parent(path)+'/people'
    person_list = model.load(people)
    dates, slots, s = prepare_people_tasks(  [ ( people, person) for person in person_list ] )
    return visualize.render(dates, slots, sorted(s), variables={'qs':urlparse.parse_qs(env['QUERY_STRING']), 'context':'/', 'path':path, 'sum':True, 'url': path+'/', 'refreshable': True }), "text/html"
render_handlers['show_team_tasks'] = show_team_tasks
    
'''
Shows the tasks of a unit grouped by sub-unit
'''    
def show_unit_tasks(path, parameters, env):
    group_container = parameters['groups']
    group_path = model.parent(path)+'/'+group_container
    groups = model.load(group_path)
    person_groups = {}
    for g in groups: 
        model.traverse(group_path+'/'+g, lambda (path, task, d): collect_persons(g, path, person_groups), all_nodes=True )    
    persons = set()
    for group in person_groups.values():
        for p in group:
            persons.add(p)        
    dates, slots, s = prepare_people_tasks( persons ) 
    schedules = {}
    for i in s:
        schedules[i[0]]=i
    group_schedules = []    
    for g in person_groups.keys():        
        group_sched = [ g, len(slots)*[0.0], 0, 0, {'url': group_path+'/'+g+'/planning/'} ]
        for _, person in person_groups[g]:
            group_sched[1] = [ group_sched[1][i] + schedules[person][1][i] for i in range(0,len(slots)) ]  
            group_sched[2] += schedules[person][2]
            group_sched[3] += schedules[person][3]
        n = len(person_groups[g])*1.0    
        group_sched[1] = [ i/n for i in group_sched[1] ]
        group_sched[2] /= n
        group_sched[3] /= n
        group_schedules.append(group_sched)    
    return visualize.render(dates, slots, sorted(group_schedules), variables={'qs':urlparse.parse_qs(env['QUERY_STRING']), 'context':'/', 'path':path, 'sum':True, 'url': path+'/', 'refreshable': False }), "text/html"    
render_handlers['show_unit_tasks'] = show_unit_tasks    
   
'''
Show the tasks of a project grouped by person
'''
def show_project(path, parameters, env):
    m=re.match(r"^.*projects/[^/]+/+([^/]+)$", path)
    project=m.group(1)
    # Find people planned on this project
    persons = set()
    model.traverse( '/', lambda p : add_if_working_on(model.normalize(p[0]), project, persons) )     
    dates, slots, s = prepare_people_tasks(  persons, project )
    return visualize.render(dates, slots, sorted(s), variables={'qs':urlparse.parse_qs(env['QUERY_STRING']), 'context':'/', 'path':path, 'sum':True, 'url': path+'/', 'refreshable': False }), "text/html"
render_handlers['show_project'] = show_project    

'''
If path points to a person, put this person in person_groups which is a dict { group: set[ (people_url, username) ]}
'''    
def collect_persons(group, path, person_groups):
    m=re.match(r"(^.*people)/[^/]+$", path)
    if m:
        people=m.group(1)
        m=re.match(r"^.*people/([^/]+)$", path)
        username=m.group(1)     
        if not group in person_groups:
            person_groups[group] = set()
        person_groups[group].add( (people, username) )
       
'''
Schedules tasks from a sequence of (people_url, person) optionally filtered to a specific project.
The returned structure is the same as scheduler.prepare_schedule.
'''       
def prepare_people_tasks(persons, project=None):
    schedules_by_date = {}
    min_date = datetime.date.today() + datetime.timedelta(days=90)
    max_date = datetime.date.today()
    n=0
    for people, person in persons:
        tasks = []
        model.traverse( people+'/'+person, lambda p : tasks.append(p[1]) )
        dates, slots, sched = scheduler.prepare_schedule(tasks, resolution=week)
        if dates[0] < min_date:
            min_date = dates[0]
        if dates[-1] > max_date:
            max_date = dates[-1]
        if dates[0] in schedules_by_date:
            l = schedules_by_date[dates[0]]
        else:
            l = []
            schedules_by_date[dates[0]] = l
        if project:
            slots = [0]*len(slots)
            for i in sched:
                if i[0].startswith(project) and not i[0] == project:
                    slots = visualize.add_list(slots, i[1])                    
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
    return dates, slots, s

'''
If path points to a task belonging to someone working on project, add (people_url, person) to persons.
'''
def add_if_working_on(path, project, persons):
    m=re.match(r"(^.*people)/([^/]+)/tasks/[^/]+/([^/]+)", path)
    if m and m.groups()[2].startswith(project):
        persons.add( (m.groups()[0], m.groups()[1]) )
        
# handlers for JIRA tasks
'''
Loads from JIRA a list of task names for the given path.
'''        
def jira_load_list(path, parameters):
    m=re.match(r"^.*people/([^/]+).*$", path)
    username=m.group(1)
    return jira.load_keys(username)
model.handlers['jira_load_list'] = jira_load_list

'''
Loads from JIRA the project names for the given path.
'''
def jira_load_projects(path, parameters):
    return jira.load_projects()
model.handlers['jira_load_projects'] = jira_load_projects   

'''
Loads the given task from JIRA
'''
def jira_load_task(path, parameters):
    m=re.match(r"^.*/([^/]+)$", path)
    key=m.group(1)
    return jira.load_task(key)    
model.handlers['jira_load_task'] = jira_load_task

# Maintenance message
message=None
def do_message(env, start_response):
    variables={"message": message,
          "qs": "",
          "path": get_path(env),
          "refreshable": False,
          'context': '/'}
    content = str(message_template(searchList=[ variables ]))
    start_response('200 OK', [('Content-Type', 'text/html'), ('Content-Length', str(len(content)))])                    
    return content
try:
    message = open("message.txt").read()
except:
    pass

# Restlite route definition
if not message:
    routes = [
        (r'GET /(?P<path>.*)', do_get),    
        (r'PUT /(?P<path>.*)', do_put),   
        (r'POST /(?P<path>.*)', do_post),   
        (r'DELETE /(?P<path>.*)', do_delete),   
    ]                
else:
    routes = [
        (r'GET /(?P<path>.*)', do_message),              
    ]

# Find the data in the home directory
if sys.platform == 'win32':
    import _winreg
    home_config = _winreg.ExpandEnvironmentStrings(u'%APPDATA%\\Platane\\')
else:
    home_config = os.path.expanduser("~"+getpass.getuser())+'/.platane/'
root=None
home_root=home_config+"root"
if os.path.exists(home_root):
    root=home_root
    model.root = root

application = restlite.router(routes)    
    
# Starts a standalone instance
if __name__ == '__main__':        
    from wsgiref.simple_server import make_server    
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)
    
    opt_parser=optparse.OptionParser()    
    opt_parser.add_option("-r", "--root", dest="root",
                      help="Root for data", metavar="ROOT")
    opt_parser.add_option("-p", "--port", dest="port",
                      help="Listen port (defaults to 7780)", metavar="PORT")
    opt_parser.add_option("-d", action="store_true", dest="debug", help="Logs debug information on the console")
    opt_parser.add_option("-n", action="store_true", dest="no_cache", help="Do not preload cache")
    opt_parser.add_option("-s", dest="solver", help="Force the underlying LP solver: 'builtin' or 'lpsolve'", metavar="SOLVER")
    (options, args) = opt_parser.parse_args()
    if options.root:
        model.root = options.root
    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)       
    else:
        logging.getLogger().setLevel(logging.INFO)
    if options.port:
        port = int(options.port)
    else:
        port = 7780            
    if options.solver:
        scheduler.solver=options.solver    
    log = logging.getLogger('platane.main')
    log.info("Using solver: "+scheduler.solver)
    httpd = make_server('', port, application)                
    log.info("Hello, platane runs on http://localhost:"+str(port)+"/")
    if not message and not options.no_cache:
        log.info("Pre-loading cached tasks...")      
        Thread(target=lambda: model.traverse("/", lambda x : "")).start()
    try: 
        httpd.serve_forever()
    except KeyboardInterrupt: pass
