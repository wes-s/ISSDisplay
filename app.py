from flask import Flask, request, render_template, make_response, send_file
from flask_restful import Api, Resource
from flask import send_from_directory
from bokeh.embed import components
from functions import *
import os

app = Flask(__name__)
api = Api(app)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'Images'),'favicon.ico', mimetype='image/png')

class getDisplay(Resource):
    # def get(self, settings):
    def get(self):
        sats = None
        key = None
        if request.args:
            key = request.args.get('key', None)
            sats = request.args.get('satellites', None)
            if sats:
                sats = sats.split(',')
        script, div = components(getChart(key,sats))
        return make_response(render_template('index.html', script=script, div=div))

# api.add_resource(getDisplay,"/getDisplay/<string:settings>")
api.add_resource(getDisplay,"/getDisplay")

#TODO work on background refresh of chart rather than kill and fill entire page
@app.route('/background_refresh')
def background_process_test():
    print("Hello")
    return "nothing"

# run.py in local werkzeug simple server when locally testing
if __name__ == "__main__":
    app.run(debug=True)