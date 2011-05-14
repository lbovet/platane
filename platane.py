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

restlite._debug = True

@restlite.resource
def root():
    def GET(request):
        try:
            return str(model.load(get_path(request)))
        except model.NotFoundException as e:
            raise restlite.Status, '404 '+str(e)
        
    def PUT(request, entity):
        print "PUT "+entity
        return "hello"
    def POST(request, entity):
        print "POST "+entity
        return "hello"
    def DELETE(request):
        print "GET"
        return "hello"        
    return locals()

def get_path(request):    
    return request['wsgiorg.routing_args']['path']

routes = [
    (r'GET,PUT,POST,DELETE /(?P<path>.*)', root),    
]        
    
if __name__ == '__main__':
    import sys
    from wsgiref.simple_server import make_server
    
    httpd = make_server('', 8080, restlite.router(routes))
    
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
