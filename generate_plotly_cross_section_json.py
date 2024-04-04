# --- generate_plotly_cross_json.py ---
# From a URL that contains the following attributes:
#   - uuid, array of flows, first UTC forecast
# lookup a single bridges json for plotting (uuid.json) from the s3 file system,
# and create a plotly plot of the short range forecast.
#
# Created by: Andy Carter, PE
# Created - 2024.02.14
# Last revised - 2024.02.21

# example URL is 
# http://127.0.0.1/xs/plotly?
#  uuid=2e8cd88c-7949-4f17-a159-83b3670f7cc0
#  &list_flows=10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180
#  &first_utc_time=2024-02-04T19:00:00

# From the URL, fetch the static bridge cross section data from uuid.json

import pytz
from datetime import datetime, timedelta
import ast # converting sting of list to list
import numpy as np
from scipy.interpolate import interp1d
import pandas as pd

import argparse
import os
import time
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import boto3
from botocore.config import Config
from urllib.parse import urlparse, parse_qs


# ======================================
def fn_interpolate_depth_from_flow(arr_flows, str_list_tup_rating):
    
    """
    Interpolates depth values from flow rates using a rating curve.

    Parameters:
    arr_flows (array): Array of flow rates for which depth values need to be interpolated.
    str_list_tup_rating (str): String representing a list of tuples containing rating curve points.

    Returns:
    Array of interpolated depth values corresponding to the input flow rates.
    """
    
    # Convert the string to a list
    list_of_tup_rating = ast.literal_eval(str_list_tup_rating)

    # Extract x and y coordinates
    x_coords, y_coords = zip(*list_of_tup_rating)

    # Find the maximum flow value in the rating curve
    max_flow_rating = max(x_coords)

    # Initialize an empty array to store the interpolated y-values
    interpolated_y_values = []

    # Perform interpolation for values within the range of the rating curve
    interp_function = interp1d(x_coords, y_coords, kind='linear', bounds_error=False)
    y_values_within_range = interp_function(arr_flows[arr_flows <= max_flow_rating])

    # Append the interpolated y-values within the range
    interpolated_y_values.extend(y_values_within_range)

    # Perform linear extrapolation for values above the maximum flow rating
    if len(arr_flows[arr_flows > max_flow_rating]) > 0:
        # Find the index of the maximum flow value in the rating curve
        max_flow_index = x_coords.index(max_flow_rating)
        
        # Calculate the slope between the last two points
        slope = (y_coords[max_flow_index] - y_coords[max_flow_index - 1]) / (x_coords[max_flow_index] - x_coords[max_flow_index - 1])
        
        # Extrapolate using linear projection
        extrapolated_y_values = y_coords[max_flow_index] + slope * (arr_flows[arr_flows > max_flow_rating] - max_flow_rating)
        
        # Append the extrapolated y-values
        interpolated_y_values.extend(extrapolated_y_values)

    # Round the y-values to the nearest 0.1
    rounded_y_values = np.round(interpolated_y_values, 1)

    return rounded_y_values
# ======================================


# .......................................
def fn_create_bridge_xs(str_static_xs_filepath, dict_url_parameters):
    
    """
    Generate a cross-section plot of a bridge with forecasted depth using Plotly.

    Parameters:
    - str_static_xs_filepath (str): The filepath of the static cross-section data.
    - dict_url_parameters (dict): A dictionary containing URL parameters.

    Returns:
    - fig4 (plotly.graph_objs._figure.Figure): The generated Plotly figure object.
    """

    #uuid  = dict_url_parameters.get('uuid', [''])[0]
    
    # Extract parameters from URL dictionary
    list_flows = ast.literal_eval(dict_url_parameters.get('list_flows', [''])[0])
    first_utc_time = dict_url_parameters.get('first_utc_time', [''])[0]
    
    # Extract S3 bucket name and file key from the static cross-section filepath
    s3_url = str_static_xs_filepath.replace("s3://", "")
    
    # Split the URL into bucket_name and file_key
    bucket_name, file_key = s3_url.split("/", 1)
    
    # Initialize an S3 client
    s3 = boto3.client('s3')
    
    # Retrieve the JSON data from the S3 object
    response = s3.get_object(Bucket=bucket_name, Key=file_key)
    
    # Load the JSON data from the response
    json_data = json.loads(response['Body'].read().decode('utf-8'))
    # ....  ....

    oldest_time = datetime.fromisoformat(first_utc_time)

    # Subtract one hour
    oldest_time_minus_hour = oldest_time - timedelta(hours=1)

    # Make the timestamp timezone-aware (assuming it's in UTC)
    oldest_time_minus_hour = oldest_time_minus_hour.replace(tzinfo=pytz.UTC)

    # Convert to the desired timezone (CDT)
    cdt = pytz.timezone('US/Central')
    forecast_time_cdt = oldest_time_minus_hour.astimezone(cdt)

    config = dict({'displayModeBar': False})
    int_hour_interval = 6  # on the depth plot, gridline interval

    list_hour = [*range(1,19,1)]

    list_str_times = []
    for i in range(1,19):
        next_time = forecast_time_cdt + timedelta(hours=i)
        str_forecast_time = "+" + str(i) + "hr: " + next_time.strftime('%a ,%b %d %I%p %Z')
        list_str_times.append(str_forecast_time)

    flt_buffer_ground = 1.0 # distance to buffer ground below lowest elevation

    config = dict({'displayModeBar': False})
    int_hour_interval = 6

    arr_flows = np.array(list_flows)
    str_list_tup_rating = json_data['hand_r']

    arr_depths = fn_interpolate_depth_from_flow(arr_flows,str_list_tup_rating)
    list_predicted_depth = arr_depths.tolist()

    # convert json's strings to lists
    list_station = ast.literal_eval(json_data['sta'])
    list_ground_elv = ast.literal_eval(json_data['ground_elv'])
    list_deck_elev = ast.literal_eval(json_data['deck_elev'])
    list_low_chord = ast.literal_eval(json_data['low_ch_elv'])

    # create a pandas dataframe of lists
    df_bridge = pd.DataFrame(list(zip(list_station,
                                      list_ground_elv,
                                      list_deck_elev,
                                      list_low_chord)),columns =['sta', 'ground_elv', 'deck_elev', 'low_chord'])

    df_bridge["max_ground_low_chord"] = df_bridge[["ground_elv", "low_chord"]].max(axis=1)

    # for now - using the average gound elevation as the water surface
    df_bridge["wsel"] = sum(list_ground_elv) / len(list_ground_elv)
    df_bridge["max_wsel_ground"] = df_bridge[["ground_elv", "wsel"]].max(axis=1)

    list_max_ground_low_chord = df_bridge["max_ground_low_chord"].tolist()
    list_max_wsel_ground = df_bridge["max_wsel_ground"].tolist()

    # list of bottom to ground to draw
    flt_lowest_elev = min(list_ground_elv) - flt_buffer_ground
    list_lowest_ground = [flt_lowest_elev for x in list_station]

    int_forecast_hour = 0 #on first render, the hour to show

    list_wsel = [x + min(list_ground_elv) for x in list_predicted_depth]
    list_of_list_max_wsel_ground = []

    for flt_wsel in list_wsel:
        df_bridge["wsel"] = flt_wsel
        df_bridge["max_wsel_ground"] = df_bridge[["ground_elv", "wsel"]].max(axis=1)
        list_max_wsel_ground = df_bridge["max_wsel_ground"].tolist()
        list_of_list_max_wsel_ground.append(list_max_wsel_ground)

    # ----- Generate a cross section plot -----
    fig4 = go.Figure()

    fig4 = make_subplots(rows=1, cols=2, subplot_titles=('Bridge Cross Section', 'Forecast of Depth' ), column_widths=[0.55, 0.35])

    # turn off the display model bar
    config = dict({'displayModeBar': False})

    # draw the lines
    fig4.add_trace(go.Scatter(x=list_station, y=list_deck_elev, name='deck',
                             hoverinfo='none',
                             line=dict(color='black', width=1.5)),
                   row=1, col=1)

    fig4.add_trace(go.Scatter(x=list_station, y=list_max_ground_low_chord,
                             fill='tonexty', name='low_chord',
                             hoverinfo='none',
                             fillcolor= 'rgba(65, 65, 65, 0.25)',
                             line=dict(color='black', width=1.5)),
                   row=1, col=1)

    int_dynamic_line_head = len(fig4.data)

    annotations_dict=[]

    # Add traces, one for each slider step
    int_count = 0

    for list_wsel_profile in list_of_list_max_wsel_ground:
        fig4.add_trace(go.Scatter(x=list_station,y=list_wsel_profile,
                                  visible=False,
                                  hoverinfo='none',
                                  line=dict(color="blue", width=3),),
                      row=1, col=1)

        # --- add the dynamic time labels
        annotations=[]    
        record = go.layout.Annotation(
            text=str(list_str_times[int_count]),
            showarrow=False,
            x=0, y=0,xref='paper',yref='paper',
            xanchor='left',yanchor='bottom',
            xshift=5,yshift=5,
            font=dict(size=18, color="black"),
            bgcolor="white",
            align="left",
        ) 
        annotations.append(record)
        annotations_dict.append(annotations)
        int_count += 1


    int_dynamic_line_tail = len(fig4.data)

    fig4.add_trace(go.Scatter(x=list_station, y=list_ground_elv,
                             fill='tonexty', name='ground',
                             hoverinfo='none',
                             fillcolor= 'rgba(0, 255, 255, 0.25)',
                             line=dict(color='black', width=3)),
                  row=1, col=1)

    fig4.add_trace(go.Scatter(x=list_station, y=list_lowest_ground,
                             fill='tonexty', name='ground fill',
                             hoverinfo='none',
                             fillcolor= 'rgba(139, 69, 19, 0.2)',
                             line=dict(color='blue', width=0)),
                  row=1, col=1)

    int_end_bridge_profiles = len(fig4.data)
    # ------------------ stage graph

    list_zone_limits = ast.literal_eval(json_data['zone_limits'])

    list_of_lists_zones = []

    for i in range(len(list_zone_limits)):
        list_of_lists_zones.append([list_zone_limits[i] for _ in list_hour])

    # --- shade in the warning zones
    fig4.add_trace(go.Scatter(x=list_hour, y=list_of_lists_zones[0], name='Zone 0',
                              mode='lines',
                             hoverinfo='none',
                             line=dict(color='grey', width=0)),
                  row=1, col=2)

    fig4.add_trace(go.Scatter(x=list_hour, y=list_of_lists_zones[1], name='Zone 1',
                              mode='lines',
                              fill='tonexty',
                              fillcolor= 'rgba(219, 165, 255, 0.40)',
                             hoverinfo='none',
                             line=dict(color='grey', width=0)),
                  row=1, col=2)

    if len(list_of_lists_zones) >= 3:
        fig4.add_trace(go.Scatter(x=list_hour, y=list_of_lists_zones[2], name='Zone 2',
                                  mode='lines',
                                  fill='tonexty',
                                  fillcolor= 'rgba(240, 0, 0, 0.18)',
                                 hoverinfo='none',
                                 line=dict(color='grey', width=0)),
                       row=1, col=2)

    if len(list_of_lists_zones) >= 4:   
        fig4.add_trace(go.Scatter(x=list_hour, y=list_of_lists_zones[3], name='Zone 3',
                                  mode='lines',
                              fill='tonexty',
                              fillcolor= 'rgba(255, 255, 3, 0.25)',
                             hoverinfo='none',
                             line=dict(color='grey', width=0)),
                      row=1, col=2)

    if len(list_of_lists_zones) >= 5: 
        fig4.add_trace(go.Scatter(x=list_hour, y=list_of_lists_zones[4], name='Zone 4',
                                  mode='lines',
                                  fill='tonexty',
                                  fillcolor= 'rgba(0, 255, 0, 0.18)',
                                  hoverinfo='none',
                                  line=dict(color='grey', width=0)),
                       row=1, col=2)

    # ---- from json data -- determine values
    str_title = json_data['anno_xs_title']
    flt_dist_to_low_ch =  json_data['min_low_ch'] - json_data['min_ground']
    list_min_low_ch = [flt_dist_to_low_ch for x in list_hour]

    # ---- draw the prediction line
    fig4.add_trace(go.Scatter(x=list_hour, y=list_predicted_depth, name='stage_graph',
                             hoverinfo='none',
                             line=dict(color='blue', width=3)),
                  row=1, col=2)

    # draw the min low chord line
    fig4.add_trace(go.Scatter(x=list_hour, y=list_min_low_ch, name='min_low_chord',
                              mode="lines",
                             hoverinfo='none',
                             line=dict(color='grey', width=2, dash='dot')),
                  row=1, col=2)

    # ----# add the 'moving dot' to the stage graph
    int_start_dots = len(fig4.data)

    i = 0
    for step in list_hour:
        fig4.add_trace(go.Scatter(
            x=[step],
            y=[list_predicted_depth[i]],
            visible=False,
            marker=dict(color="crimson", size=16),
            hoverinfo='none',
            mode="markers"),
        row=1, col=2)
        i += 1

    # --- time labels to stage graph
    list_times = []
    list_steps = [*range(0,19,int_hour_interval)]

    for i in list_steps:
        time_step = forecast_time_cdt + timedelta(hours=i)
        list_times.append(time_step)

    list_time_labels = []

    for i in list_times:
        str_hour = str(int(i.strftime('%I')))
        str_am_pm = i.strftime('%p').lower()
        str_day_of_week = i.strftime('%a')
        str_month = i.strftime('%b')
        str_day_num = str(int(i.strftime('%d')))
        str_label = str_hour + str_am_pm + '<br>' + str_day_of_week + '<br>' + str_month + ' ' + str_day_num
        list_time_labels.append(str_label)


    # Set custom x-axis labels
    fig4.update_xaxes(ticktext=list_time_labels,
                      tickvals=list_steps,
                      row=1, col=2)

    # -------------------
    str_forecast_time = forecast_time_cdt.strftime('%a ,%b %d %Y %I%p %Z')
    
    fig4['layout']['xaxis2']['title']='Site Time (' + str_forecast_time[-3:] + ")"
    fig4['layout']['yaxis2']['title']='Depth (ft)'

    # edit axes
    fig4.update_xaxes(mirror=True,
                     ticks='outside',
                     showline=True,
                     linecolor='black',
                     gridcolor='lightgrey',
                     zeroline=False,
                     fixedrange=True)

    fig4.update_yaxes(mirror=True,
                     ticks='outside',
                     showline=False,
                     linecolor='black',
                     gridcolor='lightgrey',
                     zeroline=False,
                     fixedrange=True)

    fig4.update_layout(plot_bgcolor='white',
                      paper_bgcolor='#DCDCDC',
                      showlegend=False,
                      xaxis=dict(title="Station (ft)"),
                      yaxis=dict(title="Elevation (ft)"),
                      title={'text' : '<b>' + str_title + '</b>','x':0.5,'y': 0.95,'xanchor': 'center','yanchor': 'bottom', 'font': dict(size=22)})

    # -----
    # Create and add slider
    steps = []

    for i in range(int_dynamic_line_tail - int_dynamic_line_head):
        list_render = [True] * int_dynamic_line_head + \
            [False] * (int_dynamic_line_tail - int_dynamic_line_head) + \
            [True] * (int_start_dots - int_end_bridge_profiles)

        step = dict(
            method="update",
            args=[{"visible": list_render},
                 #{"annotations": annotations_dict[i]}
                 ],
        label = "+" + str(i+1) + "hr")  # layout attribute
        step["args"][0]["visible"][i + int_dynamic_line_head] = True  # Toggle i'th trace to "visible"

        steps.append(step)

    sliders = [dict(
        active=int_forecast_hour,
        currentvalue={'visible': False},
        pad={"t": 90},
        steps=steps
    )]

    # show the desired forecast time
    fig4.data[int_dynamic_line_head + int_forecast_hour].visible = True
    fig4.data[int_start_dots + int_forecast_hour].visible = True

    str_forecast_time = forecast_time_cdt.strftime('%a, %b %d %Y %I%p %Z')

    fig4.add_annotation(text='<b>Forecast Issued: </b>' +  str_forecast_time,
                        showarrow=False,
                        x=0, y=0,xref='paper',yref='paper',
                        xanchor='left',yanchor='bottom',
                        xshift=0,yshift=-80,
                        font=dict(size=15, color="black"),
                        bgcolor="white",
                        align="left",)

    fig4.add_annotation(text=json_data['anno_latlong'],
                        showarrow=False,
                        x=0, y=0, xref='paper',yref='paper',
                        xanchor='left',yanchor='bottom',
                        xshift=5,yshift=5,
                        font=dict(size=10, color="black"),
                        bgcolor="white",
                        opacity=0.6,
                        align="left",)

    fig4.add_annotation(text=json_data['anno_nbi'],
                        showarrow=False,
                        x=0, y=0, xref='paper',yref='paper',
                        xanchor='left',yanchor='bottom',
                        xshift=5,yshift=22,
                        font=dict(size=10, color="black"),
                        bgcolor="white",
                        opacity=0.6,
                        align="left",)

    fig4.add_annotation(text=json_data['anno_comid'],
                        showarrow=False,
                        x=0, y=0, xref='paper',yref='paper',
                        xanchor='left',yanchor='bottom',
                        xshift=5,yshift=39,
                        font=dict(size=10, color="black"),
                        bgcolor="white",
                        opacity=0.6,
                        align="left",)

    fig4.update_layout(sliders=sliders)
    fig4.update_layout(margin=dict(r=25, t=70),)
    fig4.update_layout(width=1000,height=500)
    
    return(fig4)
# .......................................


# +++++++++++++++++++++
def fn_make_error_plot():
    """
    Create a plot to display an error message when bridge data is not available.

    Returns:
        plotly.graph_objects.Figure: Plotly figure displaying an error message.
    """
    # Create a new plotly figure
    fig1 = go.Figure()

    # Add a text annotation to display the error message
    fig1.add_annotation(
        x=0.5, y=0.5,
        text="Bridge Data not Available",
        showarrow=False,
        font=dict(size=48, color="red")
    )
    
    # Update layout settings
    fig1.update_layout(
        width=1000, height=500,
        xaxis_visible=False, yaxis_visible=False,  # Hide x and y axes
        plot_bgcolor="lightgray"  # Set plot background color
    )
    
    # Calculate the position to center the text within the plot area
    text_x = 0.5
    text_y = 0.5

    # Update the annotation with the calculated position
    fig1.update_annotations(x=text_x, y=text_y, xref="paper", yref="paper")
    
    return fig1
# +++++++++++++++++++++   


# -----------------------------
def fn_is_valid_s3_uri(s3_uri):
    """
    Check if a given S3 URI is valid and the corresponding object exists in the bucket.

    Parameters:
        s3_uri (str): The S3 URI to be validated.

    Returns:
        bool: True if the S3 URI is valid and the object exists, False otherwise.
    """
    # Parse the S3 URI
    parsed_uri = urlparse(s3_uri)
    bucket_name = parsed_uri.netloc
    file_name = parsed_uri.path.lstrip('/')

    # Create an S3 client
    s3 = boto3.client('s3')
    # Configure the Boto3 client with anonymous credentials for us-east-1 region
    
    '''
    s3 = boto3.client('s3', 
                      config=Config(signature_version='s3v4', 
                                    region_name='us-east-1'), 
                      aws_access_key_id='', 
                      aws_secret_access_key='')
    '''
    
    # Check if the file exists in the bucket
    try:
        s3.head_object(Bucket=bucket_name, Key=file_name)
        return True
    except:
        return False
# -----------------------------

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def validate_inputs(url, str_path_to_bridge_json_files):
    """
    Validates a cross-section plot based on JSON data retrieved from a URL.

    Parameters:
    url (str): The URL containing the JSON data.
    str_path_to_bridge_json_files (str): The path to the directory containing bridge JSON files.

    Returns:
    figure_plot: The generated cross-section plot.

    Notes:
    - The URL is expected to contain the following parameters:
      - uuid: Unique identifier for the JSON file.
      - list_flows: A list of flow values.
      - first_utc_time: The timestamp of the first data point.
    - Th

    """
    ERROR = {
    "005": "File not found with the given uuid.",
    "001": "KeyError raised during URL parsing.",
    "002": "Required parameters are missing in the URL.",
    "003a": "Non-numeric values found in the 'list_flows' parameter.",
    "003b": "Negative values found in the 'list_flows' parameter.",
    "003c": "'list_flows' parameter does not contain exactly 18 values.",
    "004": "KeyError or ValueError raised during parameter processing.",
    }
    b_valid_input = True  # Flag to track input validity
    str_static_xs_filepath = ""  # Path to the static XS file
    error_code = "000"

    try:
        parsed_url = urlparse(url)
        dict_url_parameters = parse_qs(parsed_url.query)

        # Extract UUID from URL parameters
        str_uuid = dict_url_parameters.get('uuid', [''])[0]
        # Construct path to the JSON file
        str_static_xs_filepath = os.path.join(str_path_to_bridge_json_files, str_uuid + '.json')
        
        # Check if str_static_xs_filepath exists
        if not fn_is_valid_s3_uri(str_static_xs_filepath):
            print(f'File not found at {str_static_xs_filepath}')
            b_valid_input = False
            error_code = "005"


    except KeyError:
        b_valid_input = False
        print('Error 001')
        error_code = "001"

    # Check if the required parameters are present in the URL
    list_required_params = ['uuid', 'list_flows', 'first_utc_time']
    if not all(param in dict_url_parameters for param in list_required_params):
        print('Error 002')
        b_valid_input = False
        error_code = "002"

    # Check if URL parameters contain compliant data
    try:
        # Parse 'list_flows' parameter as a list of floats
        list_flows = ast.literal_eval(dict_url_parameters['list_flows'][0])
        
        for i, item in enumerate(list_flows):
            # Check if each item is a float or an integer
            if not isinstance(item, (float, int)):
                b_valid_input = False
                print('Error 003a')
                error_code = "003a"
            # Check if each item is non-negative
            elif item < 0:
                b_valid_input = False
                print('Error 003b')
                error_code = "003b"
        
        # Check if 'list_flows' contains exactly 18 values
        if len(list_flows) != 18:
            b_valid_input = False
            print('Error 003c')
            error_code = "003c"

        # Parse 'first_utc_time' parameter as a datetime object
        first_utc_time = dict_url_parameters['first_utc_time'][0]
        datetime.fromisoformat(first_utc_time)
        
    except (KeyError, ValueError):
        b_valid_input = False
        print('Error 004')
        error_code = "004"
        
    # Create the cross-section plot if input is valid, else create an error plot
    if b_valid_input:
        return {
            "STATUS": "OK",
            "xs_file_path": str_static_xs_filepath,
            "url_params": dict_url_parameters
        }
    else:
        return {
            "STATUS": "Failed",
            "ERROR_CODE": error_code,
            "ERROR_TEXT": ERROR[error_code]
        }


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == '__main__':

    flt_start_run = time.time()
    
    parser = argparse.ArgumentParser(description='= CREATE A CROSS SECTION PLOT OF A BRIDGE FOR A SHORT RANGE FORECAST =')
    
    parser.add_argument('-i',
                        dest = "str_path_to_bridge_json_files",
                        help=r'REQUIRED: path to folder containing prepared bridge cross section JSON Example: s3://tx-bridge-xs-json/',
                        required=False,
                        default='s3://tx-bridge-xs-json/',
                        metavar='FILEPATH',
                        type=str)
    
    parser.add_argument('-u',
                        dest = "str_url",
                        help=r'REQUIRED: URL for the requested bridge Example: http://127.0.0.1/xs/?uuid=30677002-85e1-4f9d-8fbb-cdc910fd490b&list_flows=[100,200,300,400,500,600,700,800,900,1000,1100,1200,1300,1400,1500,1600,1700,1800&first_utc_time=2024-02-04T19:00:00',
                        required=False,
                        default=r'http://127.0.0.1/xs/?uuid=2e8cd88c-7949-4f17-a159-83b3670f7cc0&list_flows=100,200,300,400,500,600,700,800,900,1000,1100,1200,1300,1400,1500,1600,1700,1800&first_utc_time=2024-02-04T19:00:00',
                        metavar='STR',
                        type=str)
    
    args = vars(parser.parse_args())
    
    str_path_to_bridge_json_files = args['str_path_to_bridge_json_files']
    url = args['str_url']
    
    
    print(" ")
    print("+=================================================================+")
    print("|             CREATE A CROSS SECTION PLOT OF A BRIDGE             |")
    print("|                    FOR A SHORT RANGE FORECAST                   |")
    print("|                Created by Andy Carter, PE of                    |")
    print("|             Center for Water and the Environment                |")
    print("|                 University of Texas at Austin                   |")
    print("+-----------------------------------------------------------------+")


    print("  ---(i) INPUT JSON FILE PATH: " + str_path_to_bridge_json_files)
    print("  ---(u) URL: " + url)
    
    print("===================================================================")

    figure_plot = fn_generate_xs_from_json(url, str_path_to_bridge_json_files)
    
    flt_end_run = time.time()
    flt_time_pass = (flt_end_run - flt_start_run) // 1
    time_pass = timedelta(seconds=flt_time_pass)
    
    print('Compute Time: ' + str(time_pass))
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~