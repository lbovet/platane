import urllib
import json
import datetime
from xmlrpclib import Server

username = 'bovetl'
jira_host = 'jira'
credentials = json.load(file('credentials'))

useSoap = True

if useSoap:
    from suds.client import Client
    client = Client('http://%s/rpc/soap/jirasoapservice-v2?wsdl'%jira_host)
    auth = client.service.login(credentials['username'], credentials['password'])
    issues = client.service.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible' % username, 50)
else:
    s = Server('https://%s/rpc/xmlrpc' % jira_host)
    auth = s.jira1.login(credentials['username'], credentials['password'])
    issues = s.jira1.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible' % username)

tasks = []
for issue in issues:
    detail_string = urllib.urlopen('https://%s:%s@%s/rest/api/2.0.alpha1/issue/%s' % (credentials['username'], credentials['password'], jira_host, issue['key'])).read()
    detail = json.loads(detail_string)
    if detail['fields']['timetracking'].has_key('value') and detail['fields']['timetracking']['value'].has_key('timeestimate'):
        assignee = detail['fields']['assignee']['value']['name']
        task = {}
        task['effort'] = detail['fields']['timetracking']['value']['timeestimate'] / (8.0*60.0)
        task['name'] = issue['key']
        task['description'] = detail['fields']['summary']['value']  
        if detail['fields'].has_key('duedate') and detail['fields']['duedate'].has_key('value'):
            date_string = detail['fields']['duedate']['value'][:10]
            task['to'] = datetime.datetime.strptime(date_string, '%Y-%m-%d')    
        tasks.append(task)
    
import scheduler
print scheduler.render(tasks)
    
    