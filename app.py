from flask import Flask, request, render_template, make_response
from flask_restful import Api, Resource
from datetime import datetime
import pandas as pd
from bokeh.palettes import plasma
from bokeh.plotting import figure
from bokeh.layouts import row
from bokeh.embed import components
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import requests
import json

app = Flask(__name__)
api = Api(app)

class getDisplay(Resource):
    def get(self, settings):
        def getSunList(userLat, height):
            lat1 = 0.0
            lon1 = 0.0
            dayOfYear = float(datetime.utcnow().timetuple().tm_yday)
            minOfDay = float (datetime.utcnow().hour*60+datetime.utcnow().minute)
            declAngle = 23.45*math.sin(math.radians(360.0/365.0 * (284.99+dayOfYear)))
            brng = 0.0
            lat1 = math.radians(declAngle)
            lon1 = math.radians(-1*(360.0*(minOfDay-720)/1440.0))
            d = 10001.0
            R = 6371.0
            sunList = {}

            for i in range(0,73):
                lat2=round(math.degrees(math.asin(math.sin(lat1)*math.cos(d/R)+math.cos(lat1)*math.sin(d/R)*math.cos(math.radians(brng)))),5)
                lon2=round(math.degrees(lon1+math.atan2(math.sin(math.radians(brng))*math.sin(d/R)*math.cos(lat1),math.cos(d/R)-math.sin(lat1)*math.sin(math.radians(lat2)))),5)
                if lon2<-180:
                    lon2=lon2+360
                point = {'lat':lat2,'lon':lon2}
                sunList.update({i:point})
                brng = brng+5.0
            df = pd.DataFrame.from_dict(sunList, orient='index')
            df = df.apply(eqAzProjection,args=(userLat,height),axis=1)
            return df

        def getISSList(userLat, height):
            now = datetime.timestamp(datetime.now())
            stamp = int(now - (now%60)-1080)
            url = "https://api.wheretheiss.at/v1/satellites/25544/positions?timestamps="+ str(stamp)+",";

            for i in range(1,35):
                if i < 34:
                    url = url + str(stamp+(180*i))+ ','
                else:
                    url = url + str(stamp+(180*i))+ '&units=miles'
            
            response = requests.get(url)
            df= pd.DataFrame(columns=['latitude', 'longitude'])
            if response:
                issDf = pd.read_json(response.content)
                df = issDf[['latitude','longitude']]
            df.columns = ['lat', 'lon']
            df = df.apply(eqAzProjection,args=(userLat,height),axis=1)
            df[:]['y_raw']= (df[:]['y_raw'])
            df[:]['x_raw']= (df[:]['x_raw'])
            df[:]['y']=  df[:]['y'].astype(int)
            df[:]['x']=  df[:]['x'].astype(int)
            return df

        def eqAzProjection(s , userLat, height):
            radLat = math.radians(s['lat'])
            radLon = math.radians(s['lon'])
            if userLat >= 0:
                t1 = math.radians(90)
                lZero = math.radians(0)
            else:
                t1 = math.radians(-90)
                lZero = math.radians(0)
            c = math.acos(math.sin(t1)*math.sin(radLat)+math.cos(t1)*math.cos(radLat)*math.cos(radLon-lZero))
            k = c/math.sin(c)
            s['x'] = (k*math.cos(radLat)*(math.sin(radLon-lZero)))*(height/1.95)
            s['y'] = (k*(math.cos(t1)*math.sin(radLat)-math.sin(t1)*math.cos(radLat)*math.cos(radLon-lZero)))*(height/1.95)
            s['x_raw'] = (k*math.cos(radLat)*(math.sin(radLon-lZero)))
            s['y_raw'] = (k*(math.cos(t1)*math.sin(radLat)-math.sin(t1)*math.cos(radLat)*math.cos(radLon-lZero)))
            return s

        def getDayLightImage(userLat, height):
            sunList = getSunList(userLat,height)
            subset = sunList[['x', 'y']]
            subset[:]['x']=subset[:]['x']+500
            subset[:]['y']=subset[:]['y']+500
            
            tuples = [tuple(x) for x in subset.values]

            imFilter = Image.new('RGBA', (1000, 1000), (0, 0, 0, 0))
            draw = ImageDraw.Draw(imFilter)
            draw.polygon(tuples, fill=(0,150,100))

            imFilter = imFilter.filter(ImageFilter.GaussianBlur(15))
            if userLat >= 0:
                imFilter.transpose(Image.FLIP_TOP_BOTTOM)
            else:
                imFilter.transpose(Image.FLIP_LEFT_RIGHT)
            imFilterArray = np.array(imFilter)


            # read image as RGB and add alpha (transparency)
            if userLat >=0:
                im = Image.open('images/north_day.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            else:
                im = Image.open('images/south_day.png').convert('RGBA').transpose(Image.FLIP_LEFT_RIGHT)

            # convert to numpy (for convenience)
            imArray = np.asarray(im)

            # assemble new image (uint8: 0-255)
            newImArray = np.empty(imArray.shape,dtype='uint8')

            # colors (three first columns, RGB)
            newImArray[:,:,:3] = imArray[:,:,:3]

            # transparency (4th column)
            newImArray[:,:,3] = imFilterArray[:,:,3]

            # back to Image from numpy
            if userLat >=0:
                newIm = Image.fromarray(newImArray, "RGBA")
            else:
                newIm = Image.fromarray(newImArray, "RGBA").transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
            finalImArray = np.array(newIm)
            return finalImArray

        userLat = 35 
        height = 500
        northISSdf = getISSList(userLat,height)
        southISSdf = getISSList(-userLat,height)
        northImArray = getDayLightImage(userLat,height)
        southImArray = getDayLightImage(-userLat,height)

        ###NORTHERN HEMISPHERE
        n = figure(width=500, height=500,x_range=(-500,500), y_range=(-500,500))
        n.image_url(url=['images/north_night.png'], w=1000, h=1000, x=-500, y = 500)
        n.image_url(url=['images/north_lights.png'], w=1000, h=1000, x=-500, y = 500)
        n.image_rgba(image=[northImArray], x =-500, y=-500, dh =1000, dw=1000)
        n.line(northISSdf.x, northISSdf.y, color="blue", line_dash=[10,5], line_width=2)
        n.circle(northISSdf.loc[5]['x'], northISSdf.loc[5]['y'], color="purple", size=35, alpha = 0.5)
        n.image_url(url=['images/iss.png'], w=80, h=80, x=northISSdf.loc[5]['x']-40, y = northISSdf.loc[5]['y']+40)
        n.image_url(url=['images/corners.png'], w=1000, h=1000, x=-500, y = 500)
        n.background_fill_color = "#000000"
        n.toolbar_location = None
        n.axis.visible = False

        ###SOUTHERN HEMISPHERE
        s = figure(width=500, height=500,x_range=(-500,500), y_range=(-500,500))
        s.image_url(url=['images/south_night.png'], w=1000, h=1000, x=-500, y = 500)
        s.image_url(url=['images/south_lights.png'], w=1000, h=1000, x=-500, y = 500)
        s.image_rgba(image=[southImArray], x =-500, y=-500, dh =1000, dw=1000)
        s.line(southISSdf.x, southISSdf.y, color="blue", line_dash=[10,5], line_width=2)
        s.circle(southISSdf.loc[5]['x'], southISSdf.loc[5]['y'], color="purple", size=35, alpha = 0.5)
        s.image_url(url=['images/iss.png'], w=80, h=80, x=southISSdf.loc[5]['x']-40, y = southISSdf.loc[5]['y']+40)
        s.image_url(url=['images/corners.png'], w=1000, h=1000, x=-500, y = 500)
        s.background_fill_color = "#000000"
        s.toolbar_location = None
        s.axis.visible = False

        # output_notebook(hide_banner=True)
        # p = show(row(n, s))
        # p = row(n,s)
        script, div = components(n)
        return make_response(render_template('index.html', script=script, div=div))

api.add_resource(getDisplay,"/getDisplay/<string:settings>")

# run.py in local werkzeug simple server when locally testing
if __name__ == "__main__":
    app.run(debug=True)