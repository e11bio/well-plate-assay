import panel as pn
import param
import json
import numpy as np
import nd2
import pandas as pd

from plate_map_plots import plot_plate_map, WellInfoTable

from wellplate.elements import read_plate_xml
import holoviews as hv
from matplotlib.colors import LinearSegmentedColormap, to_hex

def get_app():
    hv.extension('plotly')
    pn.config.throttled = True

    ## Pane instances.
    well_info_table = WellInfoTable(name='')

    class ExperimentData(param.Parameterized):
        with open('app/data.json') as f:
            data_info = json.load(f)
        data_sets = data_info['data_sets']
        exp_names = [loc['name'] for loc in data_sets]
        current_exp_name = param.ObjectSelector(default=exp_names[0],objects=exp_names,label='Experiment Data')

    exp_data = ExperimentData()

    class PlateMap(param.Parameterized):
        conditions = param.ObjectSelector(default='',objects=[''],label='Condition')
        meta_data=pd.DataFrame()
        def view(self):
            print('here!')
            return plot_plate_map(plate_map,well_view)

    plate_map = PlateMap(name='')

    def hook(plot, element):
        fig = plot.state
        fig['layout']['xaxis_visible']=False
        fig['layout']['yaxis_visible']=False

    class WellView(param.Parameterized):
        xarr = None
        im_size = None
        selected_well = param.Number(0,label='Enable Brightfield Channel',precedence=-1)
        channels = []
        # 
        rgb_result_im = None
        redraw_flag = param.Boolean(False,label='Enable Brightfield Channel', precedence=-1)
        def redraw(self):
            self.redraw_flag = not self.redraw_flag
        def change_selected_well(self, attr, old, new):
            if len(new)>0:
                self.selected_well = new[0]
                # update well info.
                well_info_table.well_info = plate_map.meta_data.iloc[self.selected_well].to_frame().transpose()
        def create_result_rgb(self):
            result_im = np.zeros((self.im_size[0],self.im_size[1],3),np.float)
            for channel in self.channels:
                if channel.result_rgb is not None:
                    result_im += channel.result_rgb
            return hv.RGB(np.clip(result_im,0,1)).opts(hooks=[hook])
    well_view = WellView()


    class Channel():
        def __init__(self,name,colormap):
            self.enable = pn.widgets.Checkbox(name=f'Enable {name}', value=True)
            self.range = pn.widgets.RangeSlider(name='Display Range', start = 0, end= 2**16,
                                value=(0,20000))
            self.name = name
            self.colormap = colormap
            self.im_rgb = None
            self.result_rgb = None
            self.callback = None
        def set_data(self, array):
            self.range.start = array.min()
            self.range.end = array.max()
            #normalize.
            norm_im = array/ (2**16)
            # apply colormap.
            self.im_rgb = self.colormap(norm_im)
            # bind controls.
            self.callback = pn.bind(self.set_img_range, self.enable, self.range, watch=True)
        def set_img_range(self, enable,range, redraw=True ):
            if enable:
                if self.im_rgb is not None:
                    # scale threshold to 0-1.
                    low_lim = (range[0]/2**16)
                    high_lim = (range[1]/2**16)
                    im = self.im_rgb
                    im = (im - low_lim) / (high_lim - low_lim)
                    self.result_rgb = im[:,:,:3]
            else:
                self.result_rgb = None
            if redraw:
                well_view.redraw()



    params = well_view.param

    @pn.depends(selected_well = well_view.param.selected_well, watch=True)
    def get_well_data(selected_well):
        # Grab data from xarr.
        well_data = np.squeeze(well_view.xarr[well_view.selected_well,:,:,:]).to_numpy().astype('float')
        # attach to channels.
        for i, channel in enumerate(well_view.channels):
            channel.set_data(np.squeeze(well_data[i,:,:]))
            channel.set_img_range(channel.enable.value, channel.range.value,redraw=False)
        # trigger redraw
        well_view.redraw()

    # Redraw image.
    @pn.depends(params.redraw_flag)
    def image_callback(**kwargs):
        return well_view.create_result_rgb()
    img_dmap = hv.DynamicMap(image_callback)

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')
    # Main Layout
    # Header.
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    # Plate map.
    app.main.append(pn.Column(pn.pane.HTML("<h1>Plate Map</h1>"),plate_map.param,))
    app.main.append(pn.Row(pn.layout.HSpacer(),plate_map.view,pn.layout.HSpacer()))

    # Image widgets.
    app.main.append(pn.Column(well_info_table.param,well_info_table.view))
    channel_widgets_column = pn.Column()
    app.main.append(pn.Row(pn.layout.HSpacer(),channel_widgets_column,
        img_dmap.opts(width=600, height=600),pn.layout.HSpacer()))

    @pn.depends(exp_data.param.current_exp_name, watch=True)
    def load_experiment_data(value):
        data_index = exp_data.exp_names.index(exp_data.current_exp_name)
        meta_data, _, labels = read_plate_xml(exp_data.data_sets[data_index]['wellmap'])
        plate_map.meta_data = meta_data
        # Get conditions.
        conditions = [ cond for cond in plate_map.meta_data.columns[1:] if cond not in ['Note','Notes']]
        plate_map.param.conditions.objects = conditions
        plate_map.conditions = conditions[0]
        # load imaging data.
        well_view.xarr, names, colormaps = read_nd2(exp_data.data_sets[data_index]['nd2'])
        well_view.im_size = [well_view.xarr.shape[2],well_view.xarr.shape[3]]
        # create channels.
        well_view.channels.clear()
        for channel, channel_name in enumerate(names):
            well_view.channels.append(Channel(channel_name, colormaps[channel]))
        # Create controls.
        channel_widgets_column.clear()
        for channel in well_view.channels:
            channel_widgets_column.append(
                pn.Column(channel.enable,channel.range, background= f'{to_hex(channel.colormap(255)[:3])}60'))
            channel_widgets_column.append(pn.Column(pn.Spacer(height=5)))
    load_experiment_data(exp_data.param.current_exp_name)
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
            colors = [[0,0,0],[r,g,b]]
            # process colormaps. 
            colormaps.append(LinearSegmentedColormap.from_list('testCmap', colors, N=256))
            names.append(name)
        xarr = f.to_xarray(delayed=True)
    return xarr, names, colormaps

get_app().servable()