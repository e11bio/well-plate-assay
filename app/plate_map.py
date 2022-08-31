import panel as pn
import param
import json
import numpy as np
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Spectral6
from bokeh.transform import factor_cmap, linear_cmap
from bokeh.models import ColorBar

from wellplate.elements import read_plate_xml

def get_app():
    class ExperimentData(param.Parameterized):
        with open('app/data.json') as f:
            data_info = json.load(f)
        data_sets = data_info['data_sets']
        exp_names = [loc['name'] for loc in data_sets]
        current_exp_name = param.ObjectSelector(default=exp_names[0],objects=exp_names,label='Experiment Data')

    exp_data = ExperimentData()

    class PlateMap(param.Parameterized):
        conditions = param.ObjectSelector(default='',objects=[''],label='Condition')
        def view(self):
            return plot_plate_map()
    
    plate_map = PlateMap()

    @pn.depends(exp_data.param.current_exp_name, watch=True)
    def load_data(value):
        data_index = exp_data.exp_names.index(exp_data.current_exp_name)
        meta_data, meta_data_info, labels = read_plate_xml(exp_data.data_sets[data_index]['wellmap'])
        # Get conditions.
        conditions = [ cond for cond in meta_data.columns[1:] if cond not in ['Note','Notes']]
        plate_map.param.conditions.objects = conditions
        plate_map.meta_data=meta_data
        print(meta_data)

    load_data(None)

    # plots.
    def plot_plate_map(well_size = 96):
        p = figure(width=800, height=400, toolbar_location=None)
        p.grid.visible = False
        p.toolbar.active_drag = None
        p.toolbar.active_scroll = None
        if well_size == 96:
            x = np.tile(np.arange(1,13),8)
            y = (np.array([np.repeat(i,12)for i in range(8)])).flatten()
            #adjust axis.
            p.x_range.start, p.x_range.end = 0.5,14.5
            p.y_range.start, p.y_range.end = 7.5,-0.5
            p.yaxis.ticker = np.arange(0,9)
            p.yaxis.major_label_overrides = {0: 'A', 1: 'B', 2: 'C',3:'D',4:'E',5:'F',6:'G',7:'H'}
            p.xaxis.ticker = np.arange(1,13)

        # color.
        if plate_map.conditions != '':
            values = plate_map.meta_data[plate_map.conditions].unique()
            source = ColumnDataSource(dict(x=x,y=y,condition = plate_map.meta_data[plate_map.conditions]))
            #print(source['conditions'])
            mapper = linear_cmap(field_name='condition', palette=Spectral6 ,low=min(y) ,high=max(y))
            p.circle('x','y', source=source, radius=0.3, alpha=0.5,
                 fill_color=factor_cmap('condition', 'Category10_3', values),legend_field='condition')
            p.legend.orientation = "vertical"
            p.legend.location = "top_right"
        return p

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')

    # Main Layout
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    app.main.append(pn.Row(plate_map.param, plate_map.view))
    return app

get_app().servable()