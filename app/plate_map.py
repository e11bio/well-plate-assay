import panel as pn
import param
import json
import numpy as np
import nd2
import time

from plate_map_plots import plot_plate_map

from wellplate.elements import read_plate_xml
import holoviews as hv
from matplotlib.colors import LinearSegmentedColormap
import panel.widgets as pnw

def get_app():
    pn.extension('vtk')
    pn.config.throttled = True

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
    well_view = WellView()

    class Channel():
        def __init__(self,name,colormap):
            self.enable = pn.widgets.Checkbox(name=f'Enable {name}')
            self.range = pn.widgets.RangeSlider(name='Display Range', start = 0, end= 2**16,
                                value=(0,20000))
            self.name = name
            self.colormap = colormap
            self.im_rgb = None
            self.result_rgb = None
            self.callback = None
        def set_data(self, array):
            print(f'setting data {self.name}')
            #nmormalize.
            norm_im = array/ (2**16)
            # apply colormap.
            self.im_rgb = self.colormap(norm_im)
            # bind controls.
            self.callback = pn.bind(self.recalc_channel, self.enable, self.range, watch=True)
            print(f'setting data {self.name} Done')
        def recalc_channel(self, enable,range ):
            print(f'recalculating {self.name}')
            if enable:
                if self.im_rgb is not None:
                    print(f'recalculating {self.name}: channel enabled.')
                    # scale threshold to 0-1.
                    low_lim = (range[0]/2**16)
                    high_lim = (range[1]/2**16)
                    im = self.im_rgb
                    im = (im - low_lim) / (high_lim - low_lim)
                    self.result_rgb = im[:,:,:3]
            else:
                self.result_rgb = None
            print(f'recalculating {self.name} Done')
            well_view.redraw()

    @pn.depends(exp_data.param.current_exp_name)
    def load_data(value):
        data_index = exp_data.exp_names.index(exp_data.current_exp_name)
        meta_data, meta_data_info, labels = read_plate_xml(exp_data.data_sets[data_index]['wellmap'])
        # Get conditions.
        conditions = [ cond for cond in meta_data.columns[1:] if cond not in ['Note','Notes']]
        plate_map.param.conditions.objects = conditions
        plate_map.meta_data=meta_data
        # load imaging data.
        well_view.xarr, names, colormaps = read_nd2(exp_data.data_sets[data_index]['nd2'])
        well_view.im_size = [well_view.xarr.shape[2],well_view.xarr.shape[3]]
        # create channels.
        for channel, channel_name in enumerate(names):
            well_view.channels.append(Channel(channel_name, colormaps[channel]))
    load_data(exp_data.param.current_exp_name)

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')
    params = well_view.param

    @pn.depends(selected_well = well_view.param.selected_well, watch=True)
    def grab_image(selected_well):
        # Grab data from xarr.
        well_data = np.squeeze(well_view.xarr[well_view.selected_well,:,:,:]).to_numpy().astype('float')
        # attach to channels.
        for i, channel in enumerate(well_view.channels):
            channel.set_data(np.squeeze(well_data[i,:,:]))
        # trigger redraw
        well_view.redraw()

    ##
    # Callback on array change.
    ##
    @pn.depends(params.redraw_flag)
    def image_callback(**kwargs):
        print('redrawing')
        return create_result_rgb().opts(aspect=1)
    img_dmap = hv.DynamicMap(image_callback)

    # Create array.
    def create_result_rgb():
        print('Making result img')
        result_im = np.zeros((well_view.im_size[0],well_view.im_size[1],3),np.float)
        for channel in well_view.channels:
            if channel.result_rgb is not None:
                print(f'channel {channel.name} mean {channel.result_rgb.mean()}')
                print(f'adding {channel.name}')
                result_im += channel.result_rgb
        print(f'mean result im: {result_im.mean()}')
        print('Done')
        return hv.RGB(np.clip(result_im,0,1))

    # Main Layout
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    app.main.append(pn.Row(plate_map.param, plate_map.view))
    channel_widgets = [[channel.enable, channel.range] for channel  in well_view.channels]
    app.main.append(pn.Row(pn.Column(channel_widgets[0][0], channel_widgets[0][1]),
        img_dmap.opts(frame_width=700, xaxis=None, yaxis=None)))
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