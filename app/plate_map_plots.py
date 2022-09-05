import numpy as np
import param
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Spectral6
from bokeh.transform import factor_cmap, linear_cmap
from bokeh.models import TapTool
import panel as pn
import pandas as pd
import holoviews as hv

class WellView(param.Parameterized):
    xarr = None
    im_size = None
    selected_well = param.Number(0,label='Enable Brightfield Channel',precedence=-1)
    well_change_callback = []
    channels = []
    # 
    rgb_result_im = None
    redraw_flag = param.Boolean(False,label='Enable Brightfield Channel', precedence=-1)
    def redraw(self):
        self.redraw_flag = not self.redraw_flag
    def change_selected_well(self, attr, old, new):
        if len(new)>0:
            self.selected_well = new[0]
    def create_result_rgb(self):
        result_im = np.zeros((self.im_size[0],self.im_size[1],3),np.float)
        for channel in self.channels:
            if channel.result_rgb is not None:
                result_im += channel.result_rgb
        return hv.RGB(np.clip(result_im,0,1)).opts(hooks=[self.hook])
    def hook(self, plot, element):
        fig = plot.state
        fig['layout']['xaxis_visible']=False
        fig['layout']['yaxis_visible']=False

# plots.
def plot_plate_map(plate_map, well_view, well_size = 96):
    p = figure(width=800, height=400,tools="tap")
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

    if plate_map.conditions != '':
        values = plate_map.meta_data[plate_map.conditions].unique()
        source = ColumnDataSource(dict(x=x,y=y,condition = plate_map.meta_data[plate_map.conditions]))
        #print(source['conditions'])
        mapper = linear_cmap(field_name='condition', palette=Spectral6 ,low=min(y) ,high=max(y))
        p.circle('x','y', source=source, radius=0.3, alpha=0.5,
                fill_color=factor_cmap('condition', 'Category10_3', values),legend_field='condition')
        p.legend.orientation = "vertical"
        p.legend.location = "top_right"
        # click interactions
        p.select(type=TapTool)
        source.selected.on_change('indices', well_view.change_selected_well)
    return p

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
    def selection_change(self,selected_well):
        if self.plate_map.meta_data.size>0:
            self.well_info = self.plate_map.meta_data.iloc[selected_well].to_frame().transpose()

class Channel():
    def __init__(self,name,colormap, well_view):
        self.enable = pn.widgets.Checkbox(name=f'Enable {name}', value=True)
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