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

# Adapter to JIRA web service

import urllib
import json
import datetime
import os.path, getpass
from xmlrpclib import Server
import traceback
import logging
log = logging.getLogger('platane.jira')

jira_scheme = 'https'
jira_host = 'jira.pnet.ch'

enabled = False
credentials = None
credentials_file = os.path.expanduser("~"+getpass.getuser())+'/.platane/jira-credentials'

useSoap = True
if useSoap:
    from suds.client import Client
    logging.getLogger('suds').setLevel(logging.INFO)
    client = Client('http://%s/rpc/soap/jirasoapservice-v2?wsdl'%jira_host)
auth = None

def init():
    global credentials
    global enabled
    if credentials==None:
        try:
            credentials = json.load(file(credentials_file))
            enabled = True
        except:
            log.info('Could not load credentials from: '+credentials_file+', Jira support is disabled')    

'''
Load all active task names of a user
'''
def load_keys(username):
    init()
    log.debug("Loading keys for %s" % username)
    global auth
    if not enabled:
        return []
    try:        
        issues=[]
        if useSoap:
            if not auth:
                auth = client.service.login(credentials['username'], credentials['password'])
            tries=2
            while tries >0:
                tries-=1
                try:            
                    issues = client.service.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible and remainingEstimate > 0' % username, 50)
                    tries=0
                except:
                    auth = client.service.login(credentials['username'], credentials['password'])                 
        else:
            s = Server(jira_scheme+'://%s/rpc/xmlrpc' % jira_host)
            auth = s.jira1.login(credentials['username'], credentials['password'])
            issues = s.jira1.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible and remainingEstimate > 0' % username)
        result = list()
        for issue in issues:
            result.append(issue['key'])
        return sorted(result)
    except:
        traceback.print_exc()        
        return []

'''
Load the given issue and translate it to task attributes 
'''
def load_task(issue_key):
    init()
    log.debug("Loading %s" % issue_key)
    url = jira_scheme+'://%s:%s@%s/rest/api/2.0.alpha1/issue/%s' % (credentials['username'], credentials['password'], jira_host, issue_key)
    detail_string = urllib.urlopen(url).read()
    try:
        detail = json.loads(detail_string)
    except:
        log.error('Error decoding response from sever: %s', detail_string)
        raise 
    if 'fields' in detail and detail['fields']['timetracking'].has_key('value') and detail['fields']['timetracking']['value'].has_key('timeestimate'):
        task = {}
        task['effort'] = detail['fields']['timetracking']['value']['timeestimate'] / (8.0*60.0)
        task['name'] = issue_key
        task['link'] = jira_scheme+'://'+jira_host+"/browse/"+issue_key
        task['description'] = unicode(detail['fields']['summary']['value'])
        if detail['fields'].has_key('duedate') and detail['fields']['duedate'].has_key('value'):
            date_string = detail['fields']['duedate']['value'][:10]
            d = datetime.datetime.strptime(date_string, '%Y-%m-%d')
            task['to'] = datetime.date(d.year, d.month, d.day)  
        return task
    else:
        return None

'''
List all projects
'''
def load_projects():
    init()
    if not enabled:
        return []
    client = Client('http://%s/rpc/soap/jirasoapservice-v2?wsdl'%jira_host)
    auth = client.service.login(credentials['username'], credentials['password'])
    projects = client.service.getProjectsNoSchemes(auth)
    return sorted([ p.key for p in projects ])

if __name__ == '__main__':
    logging.basicConfig()
    import sys
    task = sys.argv[1]
    print load_task(task)
