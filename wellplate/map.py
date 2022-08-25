import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np

def read_plate_xml(file_loc):
    # get tree
    tree = ET.parse(file_loc)
    root = tree.getroot()
    # read all tag info.
    tags = []
    for elem in root.findall("./WellplateMetadata_0/Labels/"):
        # get tag info.
        tag_name = elem.find('Name').text
        tag_color = elem.find('Color').text
        # get well info.
        search_str = f"./WellplateMetadata_1/Labels/Label[Name='{tag_name}']/Wells/WellIndex"
        tag_wells_ind = np.unique(np.array([int(elem.text) for elem in root.findall(search_str)]))
        tag_wells_id = [well_ind_to_id(ind) for ind in tag_wells_ind]
        tags.append({'name':tag_name, 'tag_color':tag_color,'well_indices':tag_wells_ind,'well_ids':tag_wells_id})
    tags = pd.DataFrame(tags).drop_duplicates(subset='name')
    return tags

def well_ind_to_id(ind):
    row_col = np.unravel_index(ind,(8,12))
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    well_id = f"{letters[row_col[0]]}{row_col[1]+1}"
    return well_id