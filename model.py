import yaml

# interface 

''''
Returns the expected type for this path:
A dictionary containing:
- An 'attributes' dictionary for object types (name:type)
- A 'children' string for list types
Returns None if path does not match the schema
'''
def get_type(path):
    for i in path.split('/'):
        
    
def create(path):
    pass
    
def load(path):
    pass

# filesystem implementation

root = 'data'

schema = yaml.load(root+'/schema')
