import numpy as np
import param
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Spectral6
from bokeh.transform import factor_cmap
from bokeh.models import TapTool
import panel as pn
import pandas as pd
import holoviews as hv
import json
from wellplate.elements import read_plate_xml, read_nd2
from matplotlib.colors import  to_hex,LinearSegmentedColormap
import matplotlib.pyplot as plt
import zarr
import time

class ExperimentData(param.Parameterized):
        with open('app/data.json') as f:
            data_info = json.load(f)
        data_sets = data_info['data_sets']
        exp_names = [loc['name'] for loc in data_sets]
        current_exp_name = param.ObjectSelector(default=exp_names[0],objects=exp_names,label='Experiment Data')

class SelectedWell(param.Parameterized):
    ind = param.Number(-1,precedence=-1)

class PlateMap(param.Parameterized):
        conditions = param.ObjectSelector(default='',objects=[''],label='Condition')
        meta_data = param.DataFrame(pd.DataFrame())
        selected_well = None
        well_size = 96
        def view(self):
            p = figure(width=800, height=400,tools="tap")
            p.grid.visible = False
            p.toolbar.active_drag = None
            p.toolbar.active_scroll = None
            if self.well_size == 96:
                x = np.tile(np.arange(1,13),8)
                y = (np.array([np.repeat(i,12)for i in range(8)])).flatten()
                #adjust axis.
                p.x_range.start, p.x_range.end = 0.5,14.5
                p.y_range.start, p.y_range.end = 7.5,-0.5
                p.yaxis.ticker = np.arange(0,9)
                p.yaxis.major_label_overrides = {0: 'A', 1: 'B', 2: 'C',3:'D',4:'E',5:'F',6:'G',7:'H'}
                p.xaxis.ticker = np.arange(1,13)

            if self.conditions != '':
                values = self.meta_data[self.conditions].unique()
                source = ColumnDataSource(dict(x=x,y=y,condition = self.meta_data[self.conditions]))
                p.circle('x','y', source=source, radius=0.3, alpha=0.5,
                        fill_color=factor_cmap('condition', 'Category10_3', values),legend_field='condition')
                p.legend.orientation = "vertical"
                p.legend.location = "top_right"
                # click interactions
                p.select(type=TapTool)
                source.selected.on_change('indices', self.change_selected_well)
            return p
        def change_selected_well(self, attr, old, new):
            if len(new)>0:
                self.selected_well.ind = new[0]

        def load_experiment_data(self,current_exp_name, exp_names, data_sets):
            self.selected_flag = False
            data_index = exp_names.index(current_exp_name)
            self.meta_data, _, labels = read_plate_xml(data_sets[data_index]['wellmap'])
            # Get conditions.
            conditions = [ cond for cond in self.meta_data.columns[1:] if cond not in ['Note','Notes']]
            self.param.conditions.objects = conditions
            self.conditions = conditions[0]

class Channel():
    def __init__(self,name,colormap, enable, well_view):
        self.enable = pn.widgets.Checkbox(name=f'Enable {name}', value=enable)
        self.range = pn.widgets.RangeSlider(name='Display Range', start = 0, end= 2**16,
                            value=(0,20000))
        self.name = name
        self.colormap = colormap
        self.well_view = well_view
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
            self.well_view.redraw()

class MaskChannel(Channel):
    def set_data(self, array):
        vals = np.linspace(0,1,10000)
        np.random.shuffle(vals)
        cmap = plt.cm.jet(vals)
        cmap[0,:] = [0,0,0,0]
        cmap = plt.cm.colors.ListedColormap(cmap)
        self.im_rgb = cmap(array/10000).astype('float')
        self.callback = pn.bind(self.set_img_range, self.enable,0, watch=True)
    def set_img_range(self, enable, range, redraw=True):
        if enable:
            if self.im_rgb is not None:
                self.result_rgb = self.im_rgb[:,:,:3]
        else:
            self.result_rgb = None
        if redraw:
            self.well_view.redraw()

class WellView(param.Parameterized):
    xarr = None
    cell_masks = None
    im_size = [10,10]
    well_change_callback = []
    channels = []
    channel_widgets = pn.Column()
    # 
    redraw_flag = param.Boolean(False,label='Enable Brightfield Channel', precedence=-1)
    def redraw(self):
        self.redraw_flag = not self.redraw_flag
    def create_result_rgb(self):
        result_im = np.zeros((self.im_size[0],self.im_size[1],3),np.float)
        for channel in self.channels:
            if channel.result_rgb is not None:
                result_im += channel.result_rgb
        im = np.clip(result_im,0,1)
        im = hv.RGB(im).opts(hooks=[self.hook])
        return im
    def hook(self, plot, element):
        fig = plot.state
        fig['layout']['xaxis_visible']=False
        fig['layout']['yaxis_visible']=False
    def get_well_data(self,selected_well):
        if self.xarr is not None:
            # Grab data from xarr.
            well_data = np.squeeze(self.xarr[selected_well,:,:,:]).to_numpy().astype('float')
            mask_data = np.squeeze(self.cell_masks[selected_well,:,:]).astype('float')
            # attach to channels.
            for i, channel in enumerate(self.channels):
                if i!=len(self.channels)-1:         
                    channel.set_data(np.squeeze(well_data[i,:,:]))
                    channel.set_img_range(channel.enable.value, channel.range.value,redraw=False)
                else:
                    channel.set_data(np.squeeze(mask_data))
                    channel.set_img_range(channel.enable.value, channel.range.value,redraw=False)
            # trigger redraw
            self.redraw()
    def load_experiment_data(self,current_exp_name, exp_names, data_sets):
        data_index = exp_names.index(current_exp_name)
        # load imaging data.
        self.xarr, names, colormaps = read_nd2(data_sets[data_index]['nd2'])
        self.im_size = [self.xarr.shape[2],self.xarr.shape[3]]
        # load cell masks.
        self.cell_masks = zarr.open(data_sets[data_index]['processed'])['cells/cell_masks'].astype('float')
        # create channels.
        self.channels.clear()
        for channel, channel_name in enumerate(names):
            default_enable =True
            if (channel_name == 'Bright Field'):
                default_enable = False
            self.channels.append(Channel(channel_name, colormaps[channel], default_enable,self))
        # Create controls.
        self.channel_widgets.clear()
        for channel in self.channels:
            self.channel_widgets.append(
                pn.Column(channel.enable,channel.range, background= f'{to_hex(channel.colormap(2**16)[:3])}60'))
            self.channel_widgets.append(pn.Column(pn.Spacer(height=5)))
        # create cell mask channel.
        self.channels.append(MaskChannel('Cell Masks', None, False, self))
        mask_channel = self.channels[-1]
        self.channel_widgets.append( pn.Column(mask_channel.enable, background= f'#88888888'))
        self.channel_widgets.append(pn.Column(pn.Spacer(height=5)))


class WellInfoTable(param.Parameterized):
    #hidden.
    well_info = param.DataFrame(pd.DataFrame([{'Well':'', 'Condition':''}]),precedence=-1)
    plate_map = None
    def view(self):
        html_str = "<h1>Selected Well</h1>"
        html_str += """
        <style>
        table {
        font-family: arial, sans-serif;
        border-collapse: collapse;
        width: 100%;
        }

        td, th {
        border: 1px solid #dddddd;
        text-align: left;
        padding: 8px;
        }

        th {
        background-color: #dddddd;
        }
        </style>
        </head>
        """
        html_str += "<table><tr>"
        # column  header
        for (column_name, column_data) in self.well_info.iteritems():
            html_str += f"<th>{column_name[0].upper() + column_name[1:]}</th>"
        html_str += "</tr><tr>"
        # column data.
        for (column_name, column_data) in self.well_info.iteritems():
            html_str += f"<td>{column_data.values[0]}</td>"           
        html_str +="</tr></table><p>"
        html = pn.pane.HTML(html_str)
        return html
    def selection_change(self,selected_well, meta_data):
        if meta_data.size>0:
            self.well_info = meta_data.iloc[selected_well].to_frame().transpose()


    