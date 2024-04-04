# --- app.py ---
# This script utilizes Flask, a Python web framework, to create a web 
# application that renders cross-section plots using Plotly.io from JSON data. 
# It defines a route to handle requests for these plots, processes the data,
# and dynamically generates HTML templates to display the interactive Plotly
# plots to users.
#
# Created by: Andy Carter, PE
# Created - 2024.02.14
# # Uses the 'tx-bridge' conda environment

# --- app.py ---
# sample expeceted URL is 
# http://127.0.0.1/xs/plotly?
#  uuid=2e8cd88c-7949-4f17-a159-83b3670f7cc0
#  &list_flows=10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180
#  &first_utc_time=2024-02-04T19:00:00

# uses a plot.html in a "templates" folder to render the cross section

# Import necessary modules
from flask import Flask, render_template, send_from_directory, request, jsonify
import plotly.io as pio
import os

# import custom script and function for this Flask application
from generate_plotly_cross_section_json import fn_create_bridge_xs, validate_inputs

# Create a Flask application instance
app = Flask(__name__, static_url_path='/static', static_folder='static')

# Define a route to handle requests for the cross-section plot
@app.route('/xs/', methods=['GET'])
def get_cross_section_plot():
    try:
        # Get the URL from the request
        url = request.url
        
        str_path_to_bridge_jsons = os.environ.get('PATH_TO_BRIDGE_JSONS')

        # Path to the JSON files containing bridge data (hardcoded)
        # *********** HARD CODED *******************
        #str_path_to_bridge_jsons = 's3://txbridge-data/bridge_json/'
        # ******************************************
        validation = validate_inputs(url, str_path_to_bridge_jsons)

        if validation["STATUS"] == "OK":
            fig = fn_create_bridge_xs(validation["xs_file_path"], validation["url_params"])
            fig_html = pio.to_html(fig, full_html=True)
            return render_template('plot.html', figure=fig_html)
        else:
            return validation
    # Handle exceptions
    except Exception as e:
        # Return an error message if an exception occurs
        return f'Error: {str(e)}'
    
@app.route('/health', methods=['GET'])
def health():
    # This is where you could add checks to your service's health.
    # For a simple health check, we'll just return "up".
    return jsonify({'status': 'up'}), 200

# Run the Flask application if this script is executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0')