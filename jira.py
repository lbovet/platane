import urllib
import json
import datetime
import os.path, getpass
from xmlrpclib import Server

jira_scheme = 'https'
jira_host = 'jira.pnet.ch'
credentials = json.load(file(os.path.expanduser("~"+getpass.getuser())+'/.platane/jira-credentials'))

useSoap = True

def load_keys(username):
    if useSoap:
        from suds.client import Client
        client = Client('http://%s/rpc/soap/jirasoapservice-v2?wsdl'%jira_host)
        auth = client.service.login(credentials['username'], credentials['password'])
        issues = client.service.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible and remainingEstimate > 0' % username, 50)
    else:
        s = Server(jira_scheme+'://%s/rpc/xmlrpc' % jira_host)
        auth = s.jira1.login(credentials['username'], credentials['password'])
        issues = s.jira1.getIssuesFromJqlSearch(auth, 'resolution = Unresolved AND assignee = %s AND "User flags" = Visible and remainingEstimate > 0' % username)
    result = list()
    for issue in issues:
        result.append(issue['key'])
    return sorted(result)

def load_task(issue_key):
    url = jira_scheme+'://%s:%s@%s/rest/api/2.0.alpha1/issue/%s' % (credentials['username'], credentials['password'], jira_host, issue_key)
    detail_string = urllib.urlopen(url).read()
    detail = json.loads(detail_string)
    if detail['fields']['timetracking'].has_key('value') and detail['fields']['timetracking']['value'].has_key('timeestimate'):
        assignee = detail['fields']['assignee']['value']['name']
        task = {}
        task['effort'] = detail['fields']['timetracking']['value']['timeestimate'] / (8.0*60.0)
        task['name'] = issue_key
        task['link'] = jira_scheme+'://'+jira_host+"/browse/"+issue_key
        task['description'] = detail['fields']['summary']['value']  
        if detail['fields'].has_key('duedate') and detail['fields']['duedate'].has_key('value'):
            date_string = detail['fields']['duedate']['value'][:10]
            d = datetime.datetime.strptime(date_string, '%Y-%m-%d')
            task['to'] = datetime.date(d.year, d.month, d.day)  
        return task
    else:
        return None

if __name__ == '__main__':

    tasks = []
    for issue in load_keys('bovetl'):
        tasks.append(load_task(issue))

    print tasks
    