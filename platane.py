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

import os, thread, restlite

tree =   ('root', 
            ( 'units', (
                ( 'unit',
                    ( 'IT121',
                        ( 'people', (
                            ( 'person',
                                ( 'bovetl',
                                    ( 'tasks', (
                                        ( 'task',
                                            ( 'WGAT-73', (
                                                    ( 'priority', 0 ),
                                                    ( 'type', 'workgroup'),
                                                    ( 'due', '20.07.2011'),
                                            )),
                                        ),
                                    )),
                                ),
                            ),
                        )),
                    ),
                )),
            ),
        )
                                

@restlite.resource
def root():
    def GET(request):
        return request.response(tree)
    return locals()

# all the routes

routes = [
    (r'GET,PUT,POST /(?P<type>((xml)|(plain)))/(?P<path>.*)', 'GET,PUT,POST /%(path)s', 'ACCEPT=text/%(type)s'),
    (r'GET,PUT,POST /(?P<type>((json)))/(?P<path>.*)', 'GET,PUT,POST /%(path)s', 'ACCEPT=application/%(type)s'),
    (r'GET /root', root),    
]        

# launch the server on port 8000
    
if __name__ == '__main__':
    import sys
    from wsgiref.simple_server import make_server
    
    httpd = make_server('', 8080, restlite.router(routes))
    
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
