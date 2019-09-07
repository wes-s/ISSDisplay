from flask import Flask, request, render_template, make_response, send_file
from flask_restful import Api, Resource
from io import BytesIO
from datetime import datetime
import pandas as pd
from bokeh.palettes import plasma
from bokeh.plotting import figure, show
from bokeh.layouts import row, gridplot
from bokeh.embed import components
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import requests
import json
import ephem
from functions import *

app = Flask(__name__)
api = Api(app)

class getDisplay(Resource):
    # def get(self, settings):
    def get(self):
        script, div = components(getChart())
        return make_response(render_template('index.html', script=script, div=div))

# api.add_resource(getDisplay,"/getDisplay/<string:settings>")
api.add_resource(getDisplay,"/getDisplay")

@app.route('/background_refresh')
def background_process_test():
    print("Hello")
    return "nothing"

# run.py in local werkzeug simple server when locally testing
if __name__ == "__main__":
    app.run(debug=True)