## Copyright 2011 Laurent Bovet <laurent.bovet@windmaster.ch>
##
## This file is part of Platane.
##
## Platane is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as
## published bythe Free Software Foundation, either version 3 of the
## License, or (at your option) any later version.
##
## Platane is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public
## License along with Platane.
## If not, see <http://www.gnu.org/licenses/>.

from datetime import date, time, timedelta
import visualize
import simplex
import re
from copy import copy, deepcopy
from pprint import pprint

# constants for resolution and period
day=0
week=1
month=2

offset=0

'''
Calculate a schedule for the given tasks.
Returns a result structure: {
start: <date>,
slots: [ ],
schedule : [
{ task : <taskname>,
slots : [ ] }
]
'''
def schedule_tasks(tasks, period=week, resolution=day, work=True):
    task_dict = {}
    for i in tasks:
        task_dict[i['name']] = i
    original_task_dict = deepcopy(task_dict)
    process_super_tasks(task_dict)
    remove_overlap(task_dict, lambda t: 'absence' in t and t['absence'] )
    process_groups(task_dict)
    tasks = task_dict.values()    
    start_date, end_date, slots, category_items = itemize(tasks, resolution, work)
    s = {}
    w = {}
    all_items = {} # store all generated items for later sorting
    base_slots = copy(slots) # slots for calculating discrete load
    updated_slots = copy(slots)
    for category in sorted(category_items.keys()):
        items = category_items[category]
        all_items.update(items)
        if category < 0:
            actual_slots = base_slots
        else:
            actual_slots = updated_slots
        sched, week_effort_limit = schedule(items, original_task_dict, actual_slots, slot_size(resolution, work), start_date, end_date, resolution) 
        updated_slots = actual_slots
        s.update(sched)
        w.update(week_effort_limit)
    result = []
    # sort the items and calculate target effort for load-based tasks
    split_treated = set()
    for name in sort_schedule(all_items.values(), s):
        if all_items[name]['effort'] == 0:
            effort = sum([ t[1] for t in w[name] ])
            result.append( [name, s[name], effort, sum(s[name]), task_dict[name] ])
        else:
            result.append( [name, s[name], all_items[name]['effort'], sum(s[name]), task_dict[name] ])
    return start_date, end_date, updated_slots, result
    
    
'''
Merge slots by taking the minimum of each
'''
def merge_slots(slots, updated_slots):
    result = []
    for i in range(len(slots)):
        result.append(min(slots[i], updated_slots[i]))
    return result
    
'''
Sort the items in order of appearance. Returns the name list.
'''
def sort_schedule(items, schedule):
    s = []
    for i in items:
        j = -1
        slots = schedule[i['name']]
        start = -1
        end = 0
        for j in range(len(slots)):
            if start == -1 and slots[j] > 0:
                start = j
            if slots[j] > 0:
                end = j
        s.append( ( i['category'], i['name'] if '[' in i['name'] or i['supertask'] or i['subtask'] else ' ', i['priority'], start, end, i['name'] ) )
    s.sort()
    return [ k[5] for k in s ]
    
'''
Schedule the given items into the slots, updates the slots
'''
def schedule(items, tasks, slots, size, start_date, end_date, resolution):
    sorted_items = sorted( list(items.values()), key=lambda item: (item['from'], -item['load'], item['to']))
    week_effort_limit = max_week_effort(items, tasks, slots, start_date, end_date, resolution)
    f, A, b, edges = generate_matrix(sorted_items, slots, size, week_effort_limit, resolution)
    optimum = calculate(f, A, b)
    s = {}
    for name in items.keys():
        s[name] = [0]*len(slots)
    for i in range(0, len(edges)):
        s[edges[i][0]][edges[i][1]]=optimum[i]
        slots[edges[i][1]] = slots[edges[i][1]]-optimum[i]
    return s, week_effort_limit
    
'''
Prepare the Ax <= b matrix and vector. Also provide the corresponding edges (task, slot)
'''
def generate_matrix(items, slots, size, week_effort_limit, resolution):
    edges = []
    A = []
    b = []
    f = []
    # variable count
    n = 0
    for item in items:
        c = (item['to']-item['from']) + 1
        n = n + c
        f.extend([2**(-item['priority'])]*c)
    pos = 0
    slot_usage = {}
    # constraints on task effort
    for item in items:
        line = [0]*n
        wp=pos
        for i in range(item['from'], item['to']+1):
            edges.append( ( item['name'], i ) )
            if not slot_usage.has_key(i):
                slot_usage[i] = []
            slot_usage[i].append(pos)
            line[pos] = 1.0
            pos += 1
        if item['effort'] > 0:
            A.append(line)
            b.append(item['effort'])
        #constraint on max week effort
        if item['name'] in week_effort_limit.keys():
            week_efforts = week_effort_limit[item['name']]
            d=0
            w=0
            for week_effort in week_efforts:
                line = [0]*n
                if resolution==day:
                    for wd in range(week_effort[0]):
                        if d >= item['from'] and d <= item['to']:
                            line[wp] = 1.0
                            wp+=1
                        d+=1
                if resolution==week:
                    if w >= item['from'] and w <= item['to']:
                        line[wp] = 1.0
                        wp+=1
                if sum(line) > 0:
                    A.append(line)
                    b.append(week_effort[1])
                w+=1
    # constraints on slot capacity
    for i in sorted( slot_usage.keys() ):
        line = [0]*n
        for p in slot_usage[i]:
            line[p] = 1.0
        A.append(line)
        b.append(slots[i])
    return f, A, b, edges
    
'''
Delegate to simplex algorithm to optimize the planning.
'''
def calculate(f, A, b):
    n=len(A[0])
    fr=[ -x for x in f ]
    constraints=[]
    for i in range(0, len(A)):
        constraints.append( ( A[i], b[i] ) )
    return simplex.simplex(fr, constraints)
    
'''
Transform the task list in schedulable items and compute slots.
Returns a schedulable structure: {
start_date: <date>,
slots: [ ],
slot_size
items: { <int>, items [ ] }
}
'''
def itemize(tasks, resolution, work=True):
    start, end = bounds(tasks, resolution)
    for t in tasks:
        if not t.has_key('to') or not t['to']:
            t['to'] = end
            if t['effort'] > 0:
                end = end + timedelta(t['effort'])
    slots = []
    items = {}
    treated = {}
    i = 0
    c = -100
    for d in calendar(start, end, resolution=resolution):
        for t in tasks:
            if t.has_key('category'):
                category = t['category']
            else:
                if t.has_key('absence') and t['absence']:
                    category = c
                else:
                    category = 0                
            if not t['name'] in treated.keys():
                if category < 0:                
                    c=c+1            
                if not items.has_key(category):
                    items[category] = {}            
                items[category][t['name']] = {}
                treated[t['name']] = category
            category = treated[t['name']]
            if category in items and t['name'] in items[category].keys():
                item = items[category][t['name']]
                item['name'] = t['name']
                item['from_date'] = t['from']
                item['to_date'] = t['to']
                item['category'] = category
                item['supertask'] = t['supertask']
                item['subtask'] = t['subtask']
                if 'priority' in t:
                    item['priority'] = t['priority']
                else:
                    item['priority'] = 0
                if t.has_key('effort'):
                    item['effort'] = t['effort']
                if t.has_key('load'):
                    item['load'] = t['load']
                if i==0 or t['from'] >= d:
                    item['from'] = i
                if t['to'] < start:
                    item['to'] = 0
                if t['to'] >= d:
                    item['to'] = i
        i += 1
        if resolution==day:
            slots.append(slot_size(resolution, work))
        if resolution==week:
            slots.append(slot_size(resolution, work)-d.weekday())
    return start, end, slots, items

'''
Calculate maximum effort per week according to load and super-task in the future.

Returns in a dict per load-based item a list of tuples
corresponding to each week: (slot_start, nb_days, max_effort).
'''
def max_week_effort(items, tasks, slots, start_date, end_date, resolution):
    result = {}
    upper_bound = end_date
    for name in sorted(items.keys()):
        item = items[name]
        item_weeks = []
        if item.has_key('load') and item['load'] > 0:
            load = item['load']
        else:
            load = 1.0
        i=0
        days=0
        max_effort = 0
        super_task_name = get_super_task(name, items.keys())
        for d in calendar(start_date, upper_bound):
            days+=1
            if d >= item['from_date'] and d <= item['to_date']:                
                new_load=load
                if super_task_name:
                    super_task = get_super_task_for_day(super_task_name, d, tasks)
                    if super_task and 'load' in super_task:
                        new_load = min(load, super_task['load'])
                max_effort = max_effort + new_load * slots[i]                
            if d.weekday() == 4 or d ==upper_bound:
                # close the week
                if resolution==week:
                    max_effort = max_effort / days
                week_tuple = (days, max_effort)
                item_weeks.append(week_tuple)
                days = 0
                max_effort = 0
                if resolution==week:
                    i+=1
            if resolution==day:
                i+=1
            if i == len(slots):
                break 
        result[item['name']] = item_weeks
    return result

'''
Return the super task for the given day (may differ in case the super task is a group).
'''
def get_super_task_for_day(super_task_name, d, tasks):
    for name, task in tasks.iteritems():
        if name.startswith(super_task_name) and name.split('[')[0].strip()==super_task_name:
            if task['from'] <= d and ('to' not in task or not task['to'] or task['to'] >= d):
                return task   

'''
Move dates of overlapping tasks. Remove them if necessary.
'''
def remove_overlap(task_dict, criteria, started_wins=True):
    l = []
    for t in task_dict.values():
        if criteria(t):
            l.append( (t['from'], t) )
    new_end = date(2100, 01, 01)
    previous = None
    to_delete=set()
    for t in sorted(l):
        if previous:
            if not 'to' in previous or previous['to'] >= t[1]['from']:
                if started_wins:    
                    if not 'to' in previous or ('to' in t[1] and t[1]['to'] and t[1]['to'] <= previous['to']):
                        to_delete.add(t[1]['name'])
                    if 'to' in previous:
                        t[1]['from'] = previous['to']+timedelta(days=1)                    
                else:
                    previous['to'] = t[1]['from']-timedelta(days=1)
                    if previous['to'] < previous['from']:
                        to_delete.add(previous['name'])
        previous = t[1]
    for t in to_delete:
        del task_dict[t]        

grouped_task_re = re.compile(r'^(.*[^ ]) *\[(.+)\]$')

'''
Make grouped task disjoint
'''
def process_groups(task_dict):
    groups = set()
    for name in task_dict.keys():
        m = grouped_task_re.match(name)
        if m:
            groups.add(m.groups()[0])
    for g in groups:
        remove_overlap(task_dict, lambda t: t['name'].split('[')[0].strip()==g)

'''
Change the date of super-tasks according to sub-task dates.
'''
def process_super_tasks(tasks):
    names = tasks.keys()
    for task in tasks.values():
        task['supertask']=False
        task['subtask']=False
    for name, task in tasks.iteritems():
        m = grouped_task_re.match(name)
        if m:
            name = m.groups()[0]
        sub_tasks = get_sub_tasks(name, names)
        if len(sub_tasks) > 0:
            task['supertask']=True
            last = task['from']-timedelta(days=1)
            for sub_task in sub_tasks:
                tasks[sub_task]['subtask'] = True
                if 'to' in tasks[sub_task] and tasks[sub_task]['to']:
                    if tasks[sub_task]['to'] > last:
                        last = tasks[sub_task]['to']
            if last >= task['from']:
                task['from'] = last + timedelta(days=1)
            else:
                task['to'] = task['from']-timedelta(days=1)
        
sub_task_re = re.compile(r'^(.+)\-[0-9]+$')

'''
Return the super task name of a sub task if it has one. None otherwise.
'''
def get_super_task(sub_task_name, task_names):
    m = sub_task_re.match(sub_task_name)
    if m:
        super_task_name = m.groups()[0]
        for i in task_names:
            if i.split('[')[0].strip() == super_task_name:
                return super_task_name
    
'''
Return all subtasks of a task
'''
def get_sub_tasks(super_task_name, task_names):
    result=[]
    for t in task_names:        
        m = sub_task_re.match(t)
        if m and m.groups()[0] == super_task_name:
            result.append(t)
    return result
    
'''
Returns the first from-date and last to-date of all tasks
'''
def bounds(tasks, resolution):
    s = date.today()+timedelta(days=365)
    e = date(2000,01,01)
    for t in tasks:
        if t['from'] < s:
            s = t['from']
        if t.has_key('to') and t['to'] and t['to'] > e:
            e = t['to']
    upper = max(e+timedelta(days=14), date.today()+timedelta(days=90))
    if resolution==week:
        upper = upper + timedelta( (4 - upper.weekday()) )
    return date.today()+timedelta(days=offset), upper
    
'''
Generator of a calendar from the given date.
'''
def calendar(from_date, to_date=date(2100, 01, 01), size=None, resolution=day, work=True):
    d = from_date
    s = 0
    if resolution==day:
        while True:
            while work and d.weekday() > 4:
                d = d + timedelta(1)
            yield d
            d = d + timedelta(1)
            s+=1
            if (size and s >= size ) or d > to_date:
                break
    if resolution==week:
        while d.weekday() > 4:
            d = d + timedelta(days=1) # Jump to Monday
        while True:
            yield d
            if not d.weekday() == 0:
                d = d - timedelta(days=d.weekday())
            d = d + timedelta(days=7)
            s+=1
            if (size and s >= size ) or d > to_date:
                break
'''
Defines the slot size according to the chosen resolution.
'''
def slot_size(resolution, work=True):
    if resolution == day:
        return 1.0
    if resolution == week:
        return 5.0 if work else 7.0
        
'''
Renders a schedule
'''
def render(tasks, vars={'qs':{}, 'context':'/', 'path':'/'}, resolution=week, expand=[]):
    dates, slots, sched = prepare_schedule(tasks, resolution)
    return visualize.render(dates, slots, sched, vars, resolution, expand)

def prepare_schedule(tasks, resolution=day, work=True):
    tasks = clean_tasks(tasks)
    start, end, slots, sched = schedule_tasks(tasks, resolution=resolution)
    if resolution==week:
        slots = dailify(slots, start, end, work, False)
        for s in sched:
            s[1] = dailify(s[1], start, end, work, True)
    slots = [ 1.0-v for v in slots ]
    dates = [ c for c in calendar(start, size=len(slots)) ]
    return dates, slots, sched
            
'''
Transforms a week-based list into a day-based list.
'''
def dailify(list, start, end, work, proportional):
    result=[]
    i=0
    if work:
        week_size = 5
    else:
        week_size = 7
    for d in calendar(start, end, resolution=week):
        days= week_size - d.weekday()
        if proportional:
            ratio = days
        else:
            ratio = week_size
        if ratio>0:
            result.extend([ list[i] / float(ratio)]*days)
        else:
            result.extend([ list[i] / week_size]*days)
        i+=1
    return result
        
'''
Complete data and removes inconsistencies in tasks
'''
def clean_tasks(tasks):
    good_tasks = []
    for task in tasks:
        if not task.has_key('from') or not task['from']:
            task['from'] = date.today()
        if ('effort' in task and float(task['effort']) > 0) or ( 'load' in task and float(task['load']) > 0):
            good_tasks.append(task)
        if 'effort' in task:
            task['effort'] = float(task['effort'])
        if 'load' in task:
            task['load'] = float(task['load'])
            if task['load'] < 0:
                task['load'] = None
            if task['load'] > 1:
                task['load'] = min(1.0, task['load'] / 100.0)
    return good_tasks
        
if __name__ == '__main__':
            
    tasks = [
        { 'name' : 'absence', 'priority':-1, 'effort': 3, 'from':date(2011, 05, 24), 'to':date(2011, 05, 26) },
        { 'name' : 'architecture', 'effort': 5, 'from':date(2011, 05, 18), 'to':date(2011, 06, 8) },
        { 'name' : 'management', 'load': 0.1, 'from':date(2011, 05, 18), 'to':date(2011, 06, 10) },
        { 'name' : 'project1', 'effort': 3.5, 'from':date(2011, 05, 20), 'to':date(2011, 06, 13) },
        { 'name' : 'project2', 'priority': 1, 'effort': 3.5, 'from':date(2011, 05, 23), 'to':date(2011, 06, 13) },
        { 'name' : 'partial time', 'priority': -1, 'load': 0.2, 'from':date(2011, 05, 20), 'to':date(2011, 06, 2) }]
        
    print prepare_schedule(tasks)

