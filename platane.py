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
