import panel as pn
import param
import json

class WellData(param.Parameterized):
    with open('app/data.json') as f:
        data_loc = json.load(f)
    
    names = [loc['name'] for loc in data_loc['data_sets']]
    print(names)
    data_set = param.ObjectSelector(default=names[0],objects=names,label='Data')

well_data = WellData()

app = pn.template.MaterialTemplate(title='Plate Map')

# Main Layout
app.header.append(pn.Row(well_data.param.data_set , pn.layout.HSpacer()))

data = 'hello'

# data selection
#@pn.depends(select.value)
#def load_data(value):
#    data='test2'

pn.serve(app,num_procs=1,threaded=False)
#app.servable()
