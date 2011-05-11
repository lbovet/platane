from datetime import datetime, timedelta
from Cheetah.Template import Template
tasks_template = Template.compile(file=file('tasks.html', "r"))

'''
Renders a schedule as HTML.
'''
def render(dates, slots, tasks):
    slots = round_list(slots)
    ftasks = []
    g, separators = groups(dates, slots)
    for t in tasks:
        ftasks.append( (t[0], format(round_list(t[1]), separators, t[2]>t[3]), t[2], t[3] ) )
    vars = { 'dates' : merge(dates, separators_colors(separators)),
         'groups' : g,
         'slots' : format(slots, separators),
         'tasks' : ftasks
        }
    return str(tasks_template(searchList=[vars]))

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
        if len(week) == 0 or not week[-1][0] == d.isocalendar()[1]:
            sep = 1
            week.append( (d.isocalendar()[1], 1, slots[i]) )            
        else:
            week[-1] = ( d.isocalendar()[1], week[-1][1]+1, week[-1][2]+slots[i] )     
        if len(month) == 0 or not month[-1][0] == d.strftime('%B'):
            month.append( (d.strftime('%B'), 1, slots[i]) )        
        else:
            month[-1] = ( d.strftime('%B'), month[-1][1]+1, month[-1][2]+slots[i] )            
        if len(year) == 0 or not year[-1][0] == d.year:
            if len(year) > 0:
                sep = 1
            year.append( (d.year, 1, slots[i]) )
        else:
            year[-1] = ( d.year, year[-1][1]+1, year[-1][2]+slots[i] )
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
        return '#eeeeee' if not overflow else '#ffcccc'
    if value < 0.4:
        return '#cccccc' if not overflow else '#eeaaaa'
    if value < 0.6:
        return '#aaaaaa' if not overflow else '#dd8888'
    if value < 0.8:
        return '#888888' if not overflow else '#cc6666' 
    return '#444444' if not overflow else '#bb2222'

'''
Merges two lists in one list of 2-tuples.
'''
def merge(l, s):
    result = []
    for i in range(len(l)):
        result.append( (l[i], s[i]) )
    return result

'''
Build a list from a slot value list with coloring information.
'''
def format(l, separators, overflow=False):
    return merge([ (s, color(s, overflow)) for s in l ], separators_colors(separators))

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
        
    
if __name__ == '__main__':
        
    dates = [ datetime(2011, 05, 24)+timedelta(d) for d in range(0,20) ]
    slots = [ d/20.0 for d in range(0,20) ]
    groups, separators = groups(dates)

    vars = { 'dates' : merge(dates, separators_colors(separators)),
             'groups' : groups,
             'slots' : format(slots, separators),
             'tasks' : [ ('architecture', format([ d/40.0 for d in range(0,20) ], separators)),
                         ('project1', format([ d/60.0 for d in range(0,20) ], separators)) ]
            }

    print tasks_template(searchList=[vars])
