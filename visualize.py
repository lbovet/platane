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

# Produce the planning view by creating an intermediate structure suitable for the template

from Cheetah.Template import Template
import re
tasks_template = None # Set by main: TODO refactor

# constants for resolution and period
day=0
week=1
month=2

grouped_task_re = re.compile(r'^(.*[^ ]) *\[(.+)\]$')

'''
Renders a schedule as HTML.
'''
def render(dates, slots, tasks, variables, resolution=day, expand=[]):
    slots = round_list(slots)
    ftasks = []
    g, separators = groups(dates, slots)
    treated_groups = set()
    collapse = set()
    for task in tasks:        
        m = grouped_task_re.match(task[0])
        t = task
        group = None
        if m: 
            name = m.groups()[0]
            if m.groups()[0] not in expand:            
                if name in treated_groups:
                    continue
                t = [ name, [0]*len(task[1]), 0, 0, task ]
                missing = 0
                for grouped_task in tasks: # color_merge with from/to dates
                    m = grouped_task_re.match(grouped_task[0])
                    if m and m.groups()[0] == name:
                        t[1] = add_list(t[1], grouped_task[1])
                        missing = missing + grouped_task[2] - grouped_task[3]
                t[2] = sum(t[1])+missing
                t[3] = sum(t[1])
                treated_groups.add(name)
                collapse.add(name)        
            else:
                expand.add(name)
                group=name
        ftasks.append( {'label':t[0].replace(' ','&nbsp;'), 'slots':do_format(round_list(t[1]), separators, round(t[2],3)>round(t[3],3)), 'scheduled':t[2], 'expected':t[3], 'task':t[4], 'group':group } ) 
    all_vars = { 'dates' : color_merge(dates, separators_colors(separators)),
         'groups' : g,
         'slots' : do_format(slots, separators),
         'tasks' : ftasks,
         'collapse' : collapse,
         'expand' : expand
        }
    all_vars.update(variables)
    return str(tasks_template(searchList=[all_vars]))

'''
Add items or both lists. Returns the sum and the intersection.
'''
def add_list(l1, l2):
    result = []
    for i in range(len(l1)):
        result.append( min(1.0, l1[i] + l2[i]) )
    return result

'''
Model for year, month, week headers and week separator.
'''
def groups(dates, slots):
    year = []
    month = []
    week = []   
    separators = []
    result = { 'year' : year, 'month': month, 'week': week, 'separators': separators }
    i = 0
    for d in dates:
        sep = 0
        if len(week) == 0 or not week[-1]['label'] == d.isocalendar()[1]:
            sep = 1
            week.append( {"label":d.isocalendar()[1], "size":1, "effort": slots[i]} )            
        else:
            week[-1] = {"label": d.isocalendar()[1], "size":week[-1]['size']+1, "effort":week[-1]['effort']+slots[i] }     
        if len(month) == 0 or not month[-1]['label'] == d.strftime('%B'):
            month.append( {"label":d.strftime('%B'), "size":1, "effort":slots[i]} )        
        else:
            month[-1] = {"label": d.strftime('%B'), "size":month[-1]['size']+1, "effort":month[-1]['effort']+slots[i] }            
        if len(year) == 0 or not year[-1]['label'] == d.year:
            if len(year) > 0:
                sep = 1
            year.append( {"label":d.year, "size":1, "effort":slots[i]} )
        else:
            year[-1] = {"label": d.year, "size":year[-1]['size']+1, "effort":year[-1]['effort']+slots[i] }
        separators.append(sep)
        i+=1
    return result, separators            

'''
Coloring of slots.
'''
def color(value, overflow=False):
    if value == 0.0:
        return '#ffffff'
    if value < 0.2:
        return '#dddddd' if not overflow else '#ffcccc'
    if value < 0.4:
        return '#c0c0c0' if not overflow else '#eeaaaa'
    if value < 0.6:
        return '#aaaaaa' if not overflow else '#dd8888'
    if value < 0.8:
        return '#888888' if not overflow else '#cc6666' 
    if value < 1.0:
        return '#666666' if not overflow else '#bb4444'
    return '#444444' if not overflow else '#aa2222'

'''
Merges two lists in one list of 2-tuples.
'''
def color_merge(l, s):
    result = []
    for i in range(len(l)):
        result.append( {'item':l[i], 'separator':s[i]} )
    return result

'''
Build a list from a slot value list with coloring information.
'''
def do_format(l, separators, overflow=False):
    return color_merge([ {'slot':s, 'color':color(s, overflow)} for s in l ], separators_colors(separators))

'''
Returns a color list for a separator list.
'''
def separators_colors(separators):
    return [ ( 'lightgrey' if s ==1 else 'white' ) for s in separators ]
    
'''
Round all values of a list to a precision adequate to comparison.
'''
def round_list(l):
    return [ round(r,3) for r in l ]        
