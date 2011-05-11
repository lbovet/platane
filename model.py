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

import yaml

# interface 

''''
Returns the expected type for this path:
A dictionary containing:
- An 'attributes' dictionary for object types (name:type)
- A 'children' list containing child types
Returns None if path does not match the schema
'''
def get_type(path):
    element = root
    attributes = {}
    children = 0
    for level in path.split('/'):        
        if is_list(element):
            
            if element['children'].has_key(level):
                element = element['children'][level]
                children = [
            else:
                return None
                
    
def create(path):
    pass
    
def load(path):
    pass

# utilities

def is_list(element):
    return element.has_key('children')
    
def is_object(element):
    return element.has_key('attributes')



# filesystem implementation

root = 'data'

schema = yaml.load(root+'/schema')
