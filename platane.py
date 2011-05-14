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
from Cheetah.Template import Template

list_template = Template.compile(file=file('list.html', "r"))
task_template = Template.compile(file=file('task.html', "r"))

restlite._debug = True

def do_get(env, start_response):
    try:
        path = get_path(env)
        d = model.describe(path)
        m = model.load(path)
        start_response('200 OK', [('Content-Type', 'text/html')])        
        if d['type'] == 'leaf':
            print m
            return str(task_template(searchList=[ { 'attributes': m } ]))
        else:
            return str(list_template(searchList=[ { 'list' : m } ]))
    except model.NotFoundException as e:
        raise restlite.Status, '404 Not Found'

def do_put(env, start_response):
    pass
    
def do_post(env, start_response):
    pass

def do_delete(env, start_response):
    pass
    
def get_path(env):    
    return env['wsgiorg.routing_args']['path']

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
