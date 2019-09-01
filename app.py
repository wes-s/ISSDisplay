from flask import Flask, request, render_template, make_response
from flask_restful import Api, Resource
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

app = Flask(__name__)
api = Api(app)

class getDisplay(Resource):
    def get(self, settings):
        def getSunList(userLat, height):
            lat1 = 0.0
            lon1 = 0.0
            dayOfYear = float(datetime.utcnow().timetuple().tm_yday)
            minOfDay = float (datetime.utcnow().hour*60+datetime.utcnow().minute)
            #print(minOfDay)
            #print minOfDay
            #print('Today is day number: '+ str(dayOfYear))
            declAngle = 23.45*math.sin(math.radians(360.0/365.0 * (284.99+dayOfYear)))
            #print('The Sun is directly over: ' + str(declAngle) + ', ' + str(-1*360.0*(minOfDay-720)/1440.0))
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
            #     print('Bearing: '+str(brng)+': '+str(lat2)+', '+ str(lon2))
                #objID = int((brng+5)/5)
        #         proj = eqAzProjection(lat2, lon2, userLat, height)
                point = {'lat':lat2,'lon':lon2}#,'x':proj['x'],'y':proj['y']}
                sunList.update({i:point})
                brng = brng+5.0
            df = pd.DataFrame.from_dict(sunList, orient='index')
            df = df.apply(eqAzProjection,args=(userLat,height),axis=1)
            return df

        def getISSList():
            
            now = datetime.timestamp(datetime.now())
            
            #start in the past 18 minutes
            stamp = int(now - (now%60)-1080);
            url = "https://api.wheretheiss.at/v1/satellites/25544/positions?timestamps="+ str(stamp)+",";
            
            #append 35 more timestamps separated by 3 minutes each to the request URL
            for i in range(1,35):
                if i < 34:
                    url = url + str(stamp+(180*i))+ ','
                else:
                    url = url + str(stamp+(180*i))+ '&units=miles'

            response = requests.get(url)
            if response:
                issDf = pd.read_json(response.content)
            df = issDf#[['latitude','longitude']]
            df.columns = ['altitude', 'daynum', 'footprint', 'id', 'lat', 'lon',
            'name', 'solar_lat', 'solar_lon', 'timestamp', 'units', 'velocity',
            'visibility']
            return df
            
        def projectISSdf(df, userLat, height):
            
            #Get projected chart space X's and Y's from the projection func which adds them to the dataframe
            df = df.apply(eqAzProjection,args=(userLat,height),axis=1)
            
            #check to see if coordinate overruns boundary of chart and set to NaN
            #so the ISS path won't bleed over into the chart beside it. 
            if userLat >= 35:
                df.loc[df.eval('x<=500'), 'keepx'] = df.x
                df.loc[df.eval('x<=500'), 'keepy'] = df.y

            else:
                df.loc[df.eval('x >=-500'), 'keepx'] = df.x
                df.loc[df.eval('x>=-500'),'keepy'] = df.y
            df['x'] = df['keepx']
            df['y'] = df['keepy']
            df.drop(['keepx'], axis=1)
            df.drop(['keepy'],axis=1)    
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

        def getDay(userLat, height):
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
                im = Image.open('Images/north_day.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            else:
                im = Image.open('Images/south_day.png').convert('RGBA').transpose(Image.FLIP_LEFT_RIGHT)

                # im = day.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)

            # convert to numpy (for convenience)
            imArray = np.asarray(im)

            # create mask
            # polygon = tuples # [(100,100), (200,100), (150,150)]
            # maskIm = Image.new('L', (imArray.shape[0], imArray.shape[1]), 0)
            # ImageDraw.Draw(maskIm).polygon(polygon, outline=0, fill=1)
            # mask = np.array(maskIm)

            # assemble new image (uint8: 0-255)
            newImArray = np.empty(imArray.shape,dtype='uint8')

            # colors (three first columns, RGB)
            newImArray[:,:,:3] = imArray[:,:,:3]

            # transparency (4th column)
            # newImArray[:,:,3] = mask*255
            newImArray[:,:,3] = imFilterArray[:,:,3]

            # back to Image from numpy
            if userLat >=0:
                newIm = Image.fromarray(newImArray, "RGBA")
            else:
                newIm = Image.fromarray(newImArray, "RGBA").transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
            finalImArray = np.array(newIm)
            return finalImArray

        def getLights(userLat):
            if userLat >= 0:
                im = Image.open('Images/north_lights.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            else:
                im = Image.open('Images/south_lights.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            imArray = np.array(im)
            return imArray

        def getNight(userLat):
            if userLat >= 0:
                im = Image.open('Images/north_night.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            else:
                im = Image.open('Images/south_night.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            imArray = np.array(im)
            return imArray

        def getCorners():
            im = Image.open('Images/corners.png').convert('RGBA')
            imArray = np.array(im)
            return imArray

        def getISS():
            im = Image.open('Images/iss.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            imArray = np.array(im)
            return imArray

        userLat = 35 
        height = 500
        issList = getISSList()
        northISSdf = projectISSdf(issList, userLat, height)
        southISSdf = projectISSdf(issList, -userLat,height)
        northDay = getDay(userLat,height)
        southDay = getDay(-userLat,height)
        northNight = getNight(userLat)
        southNight = getNight(-userLat)
        northLights = getLights(userLat)
        southLights = getLights(-userLat)
        corners = getCorners()
        iss = getISS()

        c = figure(width = 1000, height = 500, x_range =(-1000, 1000), y_range=(-500, 500))
        ###NORTHERN HEMISPHERE
        # n = figure(width=500, height=500,x_range=(-500,500), y_range=(-500,500))
        c.image_rgba(image=[northNight], x =-1000, y=-500, dh =1000, dw=1000)
        c.image_rgba(image=[northLights], x =-1000, y=-500, dh =1000, dw=1000)
        c.image_rgba(image=[northDay], x =-1000, y=-500, dh =1000, dw=1000)
        c.line(northISSdf.x-500, northISSdf.y, color="blue", line_dash=[10,5], line_width=2)
        c.circle(northISSdf.loc[5]['x']-500, northISSdf.loc[5]['y'], color="purple", size=35, alpha = 0.5)
        c.image_rgba(image=[iss], x=northISSdf.loc[5]['x']-540, y = northISSdf.loc[5]['y']-40, dh =80, dw=80)
        c.image_rgba(image=[corners], x =-1000, y=-500, dh =1000, dw=1000)

        ###SOUTHERN HEMISPHERE
        # s = figure(width=500, height=500,x_range=(-500,500), y_range=(-500,500))
        c.image_rgba(image=[southNight], x =0, y=-500, dh =1000, dw=1000)
        c.image_rgba(image=[southLights], x =0, y=-500, dh =1000, dw=1000)
        c.image_rgba(image=[southDay], x =0, y=-500, dh =1000, dw=1000)
        c.line(southISSdf.x+500, southISSdf.y, color="blue", line_dash=[10,5], line_width=2)
        c.circle(southISSdf.loc[5]['x']+500, southISSdf.loc[5]['y'], color="purple", size=35, alpha = 0.5)
        c.image_rgba(image=[iss], x=southISSdf.loc[5]['x']+460, y = southISSdf.loc[5]['y']-40, dh =80, dw=80)
        c.image_rgba(image=[corners], x =0, y=-500, dh =1000, dw=1000)
        
        c.background_fill_color = "#000000"
        c.toolbar_location = None
        c.axis.visible = False
        c.border_fill_color = '#000000'

        # output_notebook(hide_banner=True)
        # p = show(row(n, s))
        # p = row(n,s)
        script, div = components(c)
        return make_response(render_template('index.html', script=script, div=div))

api.add_resource(getDisplay,"/getDisplay/<string:settings>")

# run.py in local werkzeug simple server when locally testing
if __name__ == "__main__":
    app.run(debug=True)