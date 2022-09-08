import param
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource
from bokeh.transform import factor_cmap
import numpy as np
import pandas as pd
import panel as pn
from bokeh.palettes import Category10
import nd2
import napari
from napari.utils import Colormap
from bokeh.models import TapTool

def plate_map(meta_data, viewer=None):
    pn.extension()
    plate = PlateMap()
    plate.set_meta_data(meta_data)
    if viewer is not None:
        plate.set_napari(viewer)
    return pn.Column(plate.param, plate.view)

class PlateMap(param.Parameterized):
        conditions = param.ObjectSelector(default='',objects=[''],label='Condition')
        meta_data = param.DataFrame(pd.DataFrame(), precedence=-1)
        selected_well = None
        viewer = None
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
                if values.size<10:
                    cmap_str = 'Category10_10'
                else:
                    cmap_str = 'Category20_20'
                p.circle('x','y', source=source, radius=0.3, alpha=0.5,
                        fill_color=factor_cmap('condition', cmap_str, values[(values!='None') & (values!='none')]),legend_field='condition')
                p.legend.orientation = "vertical"
                p.legend.location = "top_right"
                # click interactions
                p.select(type=TapTool)
                source.selected.on_change('indices', self.change_selected_well)
            return p
        def change_selected_well(self, attr, old, new):
            if (len(new)>0) & (self.viewer is not None):
                self.viewer.dims.set_point(0,new[0])
                # = new[0]
        def set_meta_data(self, meta_data):
            self.meta_data = meta_data
            conditions = [ cond for cond in self.meta_data.columns[1:] if cond not in ['Note','Notes','NOTES']]
            self.param.conditions.objects = conditions
            self.conditions = conditions[0]
        def set_napari(self,viewer):
            self.viewer=viewer

def napari_plate_view(nd2_loc):
    with nd2.ND2File(nd2_loc) as ndfile:
        colormaps = []
        names = []
        for channel in ndfile.metadata.channels:
            name = channel.channel.name
            names.append(name)
            r = (channel.channel.colorRGB & 0xff)/255
            g = ((channel.channel.colorRGB & 0xff00) >> 8)/255
            b = ((channel.channel.colorRGB & 0xff0000) >> 16)/255
            a = 1
            colors = [[0,0,0,0],[r,g,b,a]]
            colormaps.append(Colormap(colors,name = name))
        xarr = ndfile.to_xarray(delayed=False)
        return napari.view_image(xarr, channel_axis=1,colormap = colormaps,name=names)
