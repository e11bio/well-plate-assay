import panel as pn
import param
import json
import numpy as np
import nd2
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Spectral6
from bokeh.transform import factor_cmap, linear_cmap
from bokeh.models import ColorBar
from plate_map_plots import plot_plate_map,plot_well_view, setup_well_view

from wellplate.elements import read_plate_xml
import matplotlib.pyplot as plt
import holoviews as hv
from holoviews.streams import Pipe, Buffer
from matplotlib.colors import ListedColormap, LinearSegmentedColormap

def get_app():
    pn.extension('vtk')

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
            return plot_plate_map(plate_map,well_view)
    
    plate_map = PlateMap()

    class WellView(param.Parameterized):
        xarr = None
        selected_well = param.Number(0,label='Enable Brightfield Channel',precedence=-1)
        channel_names = None
        channel_colors= None
        # 
        channel_bf_enabled = param.Boolean(True,label='Enable Brightfield Channel')
        channel_bf_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_365_enabled = param.Boolean(True,label='Enable Channel 365')
        channel_365_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_488_enabled = param.Boolean(True,label='Enable Channel 488')
        channel_488_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_561_enabled = param.Boolean(True,label='Enable Channel 561')
        channel_561_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_640_enabled = param.Boolean(True,label='Enable Channel 640')
        channel_640_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        def change_selected_well(self, attr, old, new):
            self.selected_well = new[0]
    well_view = WellView()

    @pn.depends(exp_data.param.current_exp_name)
    def load_data(value):
        data_index = exp_data.exp_names.index(exp_data.current_exp_name)
        meta_data, meta_data_info, labels = read_plate_xml(exp_data.data_sets[data_index]['wellmap'])
        # Get conditions.
        conditions = [ cond for cond in meta_data.columns[1:] if cond not in ['Note','Notes']]
        plate_map.param.conditions.objects = conditions
        plate_map.meta_data=meta_data
        # load imaging data.
        well_view.xarr, well_view.channel_names,  well_view.channel_colors = read_nd2(exp_data.data_sets[data_index]['nd2'])
    load_data(exp_data.param.current_exp_name)

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')

    # dynamic map well images.
    def create_channel_img(im, color, enable , disp_range):
        # scale image to 0-1.
        im = im.astype('float')
        im = (im - disp_range[0]) / (disp_range[1] - disp_range[0])
        # create colormap.
        color = np.array(color)[:,0:3]
        cmp = LinearSegmentedColormap.from_list('testCmap', color, N=256)
        rgb_im = cmp(im)
        return rgb_im[:,:,0:3]

    def get_image(frame):
        result_im = np.zeros((10,10,3))
        if (well_view.xarr is not None) & bool(well_view.selected_well):
            stack = np.squeeze(well_view.xarr[well_view.selected_well,:,:,:].to_numpy())
            result_im = np.zeros((stack.shape[1],stack.shape[2],3))
            for channel in range(stack.shape[0]):
                im = np.squeeze(stack[channel,:,:])
                name = well_view.channel_names[channel]
                color = well_view.channel_colors[channel]
                if (name=='Bright Field') & (well_view.channel_bf_enabled):
                    result_im += create_channel_img(im, color,
                    well_view.channel_bf_enabled , well_view.channel_bf_range )
                if (name == '365 nm') & (well_view.channel_365_enabled):
                    result_im += create_channel_img(im, color,
                    well_view.channel_365_enabled , well_view.channel_365_range )
                if (name == '488 nm') & (well_view.channel_488_enabled):
                    result_im += create_channel_img(im, color,
                    well_view.channel_488_enabled , well_view.channel_488_range )
                if (name == '561 nm') & (well_view.channel_561_enabled):
                    result_im += create_channel_img(im, color,
                    well_view.channel_561_enabled , well_view.channel_561_range )
                if (name == '640 nm') & (well_view.channel_640_enabled):
                    result_im += create_channel_img(im, color,
                    well_view.channel_640_enabled , well_view.channel_640_range )
            result_im = (np.clip(result_im,0,1)*255).astype(np.uint8)
        return hv.RGB(result_im).opts(width=50,height=100)

    @pn.depends(selected_well=well_view.param.selected_well)
    def image_callback(selected_well):
        return get_image(selected_well).opts(responsive=True)
    img_dmap = hv.DynamicMap(image_callback)

    # Main Layout
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    app.main.append(pn.Row(plate_map.param, plate_map.view))
    #app.main.append(pn.Row( well_view.view))
    app.main.append(pn.Row(well_view.param, img_dmap))
    return app

def read_nd2(file_loc):
    colormaps = []
    names = []
    with nd2.ND2File(file_loc) as f:
        for channel in f.metadata.channels:
            name = channel.channel.name
            r = (channel.channel.colorRGB & 0xff)/255
            g = ((channel.channel.colorRGB & 0xff00) >> 8)/255
            b = ((channel.channel.colorRGB & 0xff0000) >> 16)/255
            a = 1
            colors = [[0,0,0,0],[r,g,b,a]]
            colormaps.append(colors)
            names.append(name)
        xarr = f.to_xarray(delayed=True)
    return xarr, names, colormaps

get_app().servable()