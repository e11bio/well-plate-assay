import panel as pn
import param
import json
import numpy as np
import pandas as pd

from plate_map_plots import  PlateMap, WellInfoTable, WellView, Channel

from wellplate.elements import read_plate_xml, read_nd2
import holoviews as hv
from matplotlib.colors import  to_hex

def get_app():
    hv.extension('plotly')
    pn.config.throttled = True

    class ExperimentData(param.Parameterized):
        with open('app/data.json') as f:
            data_info = json.load(f)
        data_sets = data_info['data_sets']
        exp_names = [loc['name'] for loc in data_sets]
        current_exp_name = param.ObjectSelector(default=exp_names[0],objects=exp_names,label='Experiment Data')

    exp_data = ExperimentData()

    # instantiate
    # plate map.
    plate_map = PlateMap(name='')
    plate_map.exp_data = exp_data
    plate_map.bound = pn.bind(plate_map.load_experiment_data, exp_data.param.current_exp_name)
    # well view.
    well_view = WellView()
    well_view.exp_data = exp_data
    well_view.bound = pn.bind(well_view.get_well_data, plate_map.param.selected_well)
    well_view.bound_exp = pn.bind(well_view.load_experiment_data, exp_data.param.current_exp_name)
    # info table.
    well_info_table = WellInfoTable(name='')
    well_info_table.plate_map = plate_map
    well_info_table.bound = pn.bind(well_info_table.selection_change, plate_map.param.selected_well)

    # Redraw image.
    @pn.depends(well_view.param.redraw_flag)
    def image_callback(**kwargs):
        return well_view.create_result_rgb()
    img_dmap = hv.DynamicMap(image_callback)

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')
    # Main Layout
    # Header.
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    # Plate map.
    app.main.append(pn.Column(plate_map.bound,plate_map.param.conditions,))
    app.main.append(pn.Row(pn.layout.HSpacer(),plate_map.view,pn.layout.HSpacer()))

    # Image widgets.
    app.main.append(pn.Column(well_info_table.bound,well_info_table.param,well_info_table.view))
    app.main.append(pn.Row(pn.layout.HSpacer(),well_view.bound,well_view.bound_exp,well_view.channel_widgets,
    img_dmap.opts(width=700, height=700),pn.layout.HSpacer()))
    return app



get_app().servable()