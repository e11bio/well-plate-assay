import numpy as np
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.palettes import Spectral6
from bokeh.transform import factor_cmap, linear_cmap
from bokeh.models import ColorBar, TapTool
import matplotlib.pyplot as plt
import panel as pn
from random import randrange

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

def plot_well_view(well_view):
    fig, ax = plt.subplots(1,1, figsize=(10, 8))
    if (well_view.xarr is not None) & bool(well_view.selected_well):
        stack = np.squeeze(well_view.xarr[well_view.selected_well,:,:,:])
        for channel in range(stack.shape[0]):
            im = np.squeeze(stack[channel,:,:])
            name = well_view.channel_names[channel]
            color = well_view.channel_colors[channel]
            if name=='Bright Field':
                im = create_channel_img(im.to_numpy(), color, well_view.channel_bf_enabled , well_view.channel_bf_range )
                print(f"{name}; {color}")
                print(im.min())
                ax.imshow(im, cmap="hot")

                #p.image(image=im, x=0, y=0, dw=10, dh=10, palette="Spectral11", level="image")
    else:
        im = np.zeros((well_view.xarr.shape[2],well_view.xarr.shape[3]))
    return fig

def create_channel_img(im, color, enable , disp_range):
    return im