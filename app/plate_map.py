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
        selected_well = param.Number(0,label='Enable Brightfield Channel',precedence=-1)
        channel_names = None
        channel_colormaps= None
        raw_well = np.zeros((3,3,3))
        rgb_well = None
        # 
        rgb_result_im = None
        bf_rgb = None
        redraw = param.Boolean(False,label='Enable Brightfield Channel', precedence=-1)
        channel_bf_enabled = param.Boolean(True,label='Enable Brightfield Channel')
        channel_bf_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_365_enabled = param.Boolean(False,label='Enable Channel 365')
        channel_365_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_488_enabled = param.Boolean(False,label='Enable Channel 488')
        channel_488_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_561_enabled = param.Boolean(False,label='Enable Channel 561')
        channel_561_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        channel_640_enabled = param.Boolean(False,label='Enable Channel 640')
        channel_640_range = param.Range(default=(200, 20000), bounds=(0, 65536),label='Display Range')
        def change_selected_well(self, attr, old, new):
            if len(new)>0:
                print('here')
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
        well_view.xarr, well_view.channel_names,  well_view.channel_colormaps = read_nd2(exp_data.data_sets[data_index]['nd2'])
    load_data(exp_data.param.current_exp_name)

    # Create app.
    app = pn.template.MaterialTemplate(title='Plate Map')

    # dynamic map well images.
    def create_channel_img(im,disp_range):
        # scale threshold to 0-1.
        low_lim = (disp_range[0]/2**16)
        high_lim = (disp_range[1]/2**16)
        im = (im - low_lim) / (high_lim - low_lim)
        return im
        
    params = well_view.param

    @pn.depends(selected_well = well_view.param.selected_well, watch=True)
    def grab_image(selected_well):
        # apply colormap to full range
        well_view.raw_well = np.squeeze(well_view.xarr[well_view.selected_well,:,:,:]).to_numpy().astype('float')
        well_view.rgb_well = []
        for channel, cmap in enumerate(well_view.channel_colormaps):
            # 0-2^16 -> 0-1
            norm_im = well_view.raw_well[channel,:,:] / (2**16)
            well_view.rgb_well.append(cmap(norm_im)[:,:,:3])
        recalc_channel(name= 'Bright Field', output_name = 'bf_rgb',
         enabled = well_view.channel_bf_enabled, range = well_view.channel_bf_range)
        well_view.redraw = not well_view.redraw

    ##
    # Callback on array change.
    ##
    @pn.depends(params.redraw)
    def image_callback(**kwargs):
        return create_result_rgb().opts(aspect=1)
    img_dmap = hv.DynamicMap(image_callback)

    # Create array.
    def create_result_rgb():
        result_im = np.zeros((well_view.raw_well.shape[1],well_view.raw_well.shape[2],3),np.float)
        if well_view.bf_rgb is not None:
            result_im+= well_view.bf_rgb
        return hv.RGB(np.clip(result_im,0,1))

    ##
    # CHannel Controls.
    ##
    # BF
    class Channel():
        
        def __init__(self,name):
            self.enable = pn.widgets.Checkbox(name=f'Enable {name}')
            self.range = pn.widgets.RangeSlider(name='Display Range', start = 0, end= 2**16,
                                value=(0,20000))
            self.name = name
            result_rgb = None
        def test(self,a):
            print('test complete')
        def recalc_channel(self, enable,range ):
            print('here')
            if enable & (self.name in well_view.channel_names):
                channel_ind = well_view.channel_names.index(self.name)
                if well_view.rgb_well is not None:
                    self.result_rgb = create_channel_img(well_view.rgb_well[channel_ind], range )
            else:
                self.result_rgb = None
    
    test = Channel('Bright Field')
    channel_callback = pn.bind(test.recalc_channel, test.enable, test.range, watch=True)

    @pn.depends(params.channel_bf_enabled, params.channel_bf_range, watch=True)
    def recalc_bf(enabled, range):
        if enabled & ('Bright Field' in well_view.channel_names):
            channel_ind = well_view.channel_names.index('Bright Field')
            well_view.bf_rgb = create_channel_img(well_view.rgb_well[channel_ind], well_view.channel_bf_range )
        else:
            well_view.bf_rgb = None
        well_view.redraw = not well_view.redraw



    # Main Layout
    app.header.append(pn.Row(exp_data.param.current_exp_name , pn.layout.HSpacer()))
    app.main.append(pn.Row(plate_map.param, plate_map.view))
    app.main.append(pn.Row(pn.Column(test.enable,test.range ),
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