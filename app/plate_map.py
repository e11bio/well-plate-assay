import panel as pn
import param
import json
import numpy as np
import pandas as pd

from plate_map_plots import  PlateMap, WellInfoTable, WellView, ExperimentData, SelectedWell

from wellplate.elements import read_plate_xml, read_nd2
import holoviews as hv
from matplotlib.colors import  to_hex
from holoviews.operation.datashader import regrid

def get_app():
    hv.extension('plotly')
    pn.config.throttled = True

    # instantiate
    exp_data = ExperimentData()
    selected_well = SelectedWell()
    # plate map.
    plate_map = PlateMap(name='')
    plate_map.selected_well = selected_well
    plate_map.bound = pn.bind(plate_map.load_experiment_data, exp_data.param.current_exp_name,
        exp_data.exp_names,exp_data.data_sets)
    # well view.
    well_view = WellView()
    well_view.bound = pn.bind(well_view.get_well_data, selected_well.param.ind)
    well_view.bound_exp = pn.bind(well_view.load_experiment_data, exp_data.param.current_exp_name,
        exp_data.exp_names,exp_data.data_sets)
    # info table.
    well_info_table = WellInfoTable(name='')
    well_info_table.bound = pn.bind(well_info_table.selection_change,
        selected_well.param.ind, plate_map.param.meta_data)

    # Main image viewer.
    @pn.depends(well_view.param.redraw_flag)
    def image_callback(**kwargs):
        return well_view.create_result_rgb()
    img_dmap = hv.DynamicMap(image_callback)
    regridded = regrid(img_dmap)
    display_obj = regridded.opts(width=700, height=700,aspect=1)

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
    app.main.append(pn.Row(pn.layout.HSpacer(),
    well_view.bound,well_view.bound_exp,
    well_view.channel_widgets,display_obj,pn.layout.HSpacer()))
    return app

get_app().servable()