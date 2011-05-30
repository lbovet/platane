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

from datetime import date, time, timedelta
import visualize
import simplex
from copy import copy
from pprint import pprint   

# constants for resolution and period
day=0
week=1
month=2

offset=-1

'''
Calculate a schedule for the given tasks.
Returns a result structure: {
start: <date>,
slots: [   ],
schedule : [
   { task : <taskname>, 
     slots : [ ] }
]
'''
def schedule_tasks(tasks, period=week, resolution=day, work=True):
    task_dict = {}
    for i in tasks:
        task_dict[i['name']] = i
    start_date, end_date, slots, category_items = itemize(tasks, resolution, work)    
    s = {}
    w = {}
    all_items = {}  # store all generated items for later sorting
    base_slots = copy(slots) # slots for calculating discrete load
    for category in sorted(category_items.keys()):
        items = category_items[category]    
        all_items.update(items)
        sched, week_effort_limit = schedule(items, slots, slot_size(resolution, work), start_date, end_date,  resolution)
        s.update(sched)    
        w.update(week_effort_limit)
        if category < 0:
            base_slots = copy(slots)
    result = []
    # sort the items and calculate target effort for load-based tasks
    split_treated = set()
    for name in sort_schedule(all_items.values(), s):
        if all_items[name]['effort'] == 0:
            effort = sum([ t[1] for t in w[name] ])
            result.append( [name, s[name], effort, sum(s[name]), task_dict[name] ]) 
        else:
            result.append( [name, s[name], all_items[name]['effort'], sum(s[name]), task_dict[name] ]) 
    return start_date, end_date, slots, result
    
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
        s.append( ( i['priority'], start, -i['load'], end, i['name'] ) )
    s.sort()
    return [ k[4] for k in s ]
    
'''
Schedule the given items into the slots, updates the slots
'''
def schedule(items, slots, size, start_date, end_date, resolution):
    sorted_items = sorted( list(items.values()), key=lambda item: (item['from'], -item['load'], item['to']))
    week_effort_limit = max_week_effort(items, slots, start_date, end_date, resolution)        
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
    i = 0
    for d in calendar(start, end, resolution=resolution):        
        for t in tasks:
            if t.has_key('category'):
                category = t['category']
            else:
                category = 0
            if not items.has_key(category):
                items[category] = {}
            if not items[category].has_key(t['name']):
                items[category][t['name']] = {}
            item = items[category][t['name']]
            item['name'] = t['name']
            item['from_date'] = t['from']
            item['to_date'] = t['to']
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
Calculate maximum effort per week according to load (and super-task in the future).

Returns in a dict per load-based item a list of tuples 
corresponding to each week: (slot_start, nb_days, max_effort).
'''
def max_week_effort(items, slots, start_date, end_date, resolution):
    result = {}
    upper_bound = end_date
    for k,item in items.iteritems():
        item_weeks = []
        if item.has_key('load') and item['load'] > 0:        
            load = item['load']
        else:
            load = 1.0
        i=0
        days=0
        max_effort = 0
        for d in calendar(start_date, upper_bound):
            days+=1
            if d >= item['from_date'] and d <= item['to_date']:
                max_effort = max_effort + load * slots[i]              
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
def render(tasks, vars={'qs':{}, 'context':'/', 'path':'/'}, resolution=week):
    dates, slots, sched = prepare_schedule(tasks, resolution)
    return visualize.render(dates, slots, sched, vars, resolution)

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
        print d, days, ratio
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
            if  task['load'] > 1:
                task['load'] = min(1.0, task['load'] / 100.0)
    return good_tasks
        
if __name__ == '__main__':
            
    tasks = [ 
        { 'name' : 'absence', 'priority':-1, 'effort': 3, 'from':date(2011, 05, 24), 'to':date(2011, 05, 26) },
        { 'name' : 'architecture', 'effort': 5, 'from':date(2011, 05, 18), 'to':date(2011, 06, 8) },        
        { 'name' : 'management', 'load': 0.1, 'from':date(2011, 05, 18), 'to':date(2011, 06, 10) },        
        { 'name' : 'project1',  'effort': 3.5, 'from':date(2011, 05, 20), 'to':date(2011, 06, 13) },
        { 'name' : 'project2', 'priority': 1, 'effort': 3.5, 'from':date(2011, 05, 23), 'to':date(2011, 06, 13) },
        { 'name' : 'partial time', 'priority': -1, 'load': 0.2, 'from':date(2011, 05, 20), 'to':date(2011, 06, 2) }]
        
    print prepare_schedule(tasks)
