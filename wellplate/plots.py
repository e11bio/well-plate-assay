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
import zarr
from wellplate.extract import nd2_file_2_zarr_result_file

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

def show_sig_cell_masks(nd2_file, well_ind, dapi_channel, scaffold_channel, threshold_factor = 0.5 ):
  # get result zarr file. 
  result_file = nd2_file_2_zarr_result_file(nd2_file)
  proc_data = zarr.open(result_file)
  # read nd2 file.
  im_data, channel_names, colormaps = read_nd2(nd2_file)
  channel_ind = channel_names.index(scaffold_channel)
  # get image.
  im=im_data[well_ind,channel_ind,:,:].to_numpy()
  # get intensities.
  intensities = proc_data[f'cells/intensities/well {well_ind}/channel {scaffold_channel}'][:]
  # get background values.
  background_values = proc_data[f'cells/background/well {well_ind}/channel {scaffold_channel}'][:]
  mean_background = background_values[0]
  std_background = background_values[1]
  # THRESHOLD.
  threshold = mean_background+(threshold_factor*std_background)
  sig_cells = np.argwhere(intensities>threshold)+1
  ns_cells = np.argwhere(intensities<=threshold)+1
  # get mask.
  mask_im = proc_data[f'cells/masks/well {well_ind}/channel {dapi_channel}'][:]
  # get significant mask image.
  sig_mask = np.isin(mask_im,sig_cells)
  sig_mask = np.ma.masked_equal(sig_mask, False)
  ns_mask = np.isin(mask_im,ns_cells)
  ns_mask = np.ma.masked_equal(ns_mask, False)
  cm_sig = mpl.colors.ListedColormap(['black','green'])
  cm_ns = mpl.colors.ListedColormap(['black','red'])
  # make figure.
  fig, ax = plt.subplots(1,1,figsize=(12,12))
  ax.imshow(im,vmin=intensities.min(),vmax=np.percentile(intensities,80),cmap='gray')
  ax.imshow(sig_mask, cmap=cm_sig, vmin=0, vmax=1, interpolation='none', alpha=0.25)
  ax.imshow(ns_mask, cmap=cm_ns, vmin=0, vmax=1, interpolation='none', alpha=0.25)