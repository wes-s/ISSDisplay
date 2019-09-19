from datetime import datetime
import pandas as pd
from bokeh.palettes import viridis
from bokeh.plotting import figure, show, output_notebook
from bokeh.layouts import row
from bokeh.embed import components
from bokeh.models import Label
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import requests
import json
import ephem
def dmsToDecDeg(dms):
    deg = float(dms[0])
    min = float(dms[1])/60
    sec = float(dms[2])/3600 
    sign = float(np.sign(deg))

    if deg <0:
        decDeg = math.copysign((math.fabs(deg) + min + sec),deg)
    else:
        decDeg = deg+ min + sec
    return decDeg

def getSunList(userLat, height):
    lat1 = 0.0
    lon1 = 0.0
    dayOfYear = float(datetime.utcnow().timetuple().tm_yday)
    minOfDay = float (datetime.utcnow().hour*60+datetime.utcnow().minute)
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
        point = {'lat':lat2,'lon':lon2}
        sunList.update({i:point})
        brng = brng+5.0
    df = pd.DataFrame.from_dict(sunList, orient='index')
    df = df.apply(eqAzProjection,args=(userLat,height),axis=1)
    return df

def getMoonLocation(userLat, height):
    home = ephem.Observer()
    if userLat >= 0:
        home.lat, home.lon = -90, 0 
    else:
        home.lat, home.lon = -90, 0

    home.date = datetime.utcnow()

    moon = ephem.Moon()
    moon.compute(home)

    lat1= dmsToDecDeg(str(moon.dec).split(':'))
    lon1= dmsToDecDeg(str(moon.az).split(':'))
    point =  {0:{'lat':lat1,'lon':lon1}}
    df = pd.DataFrame.from_dict(point, orient='index')
    df = df.apply(eqAzProjection,args=(userLat, height), axis=1)
    return df

def getMoonList():
    home = ephem.Observer()
    home.lat, home.lon = -90, 0
    home.date = datetime.utcnow()
    moon = ephem.Moon()
    moon.compute(home)

    lat1= math.radians(dmsToDecDeg(str(moon.dec).split(':')))
    lon1= math.radians(dmsToDecDeg(str(moon.az).split(':')))

    d = 10001.0
    R = 6371.0
    brng = 0.0

    moonList = {}
    for i in range(0,73):
        lat2=round(math.degrees(math.asin(math.sin(lat1)*math.cos(d/R)+math.cos(lat1)*math.sin(d/R)*math.cos(math.radians(brng)))),10)
        lon2=round(math.degrees(lon1+ math.atan2(math.sin(math.radians(brng))*math.sin(d/R)*math.cos(lat1),math.cos(d/R)-math.sin(lat1)*math.sin(math.radians(lat2)))),10)
        if lon2<-180:
            lon2=lon2+360
        if lon2>180:
            lon2 = lon2-360
        point = {'lat':lat2,'lon':lon2}
        moonList.update({i:point})
        brng = brng+5.0
    df = pd.DataFrame.from_dict(moonList, orient='index')
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
        df = pd.read_json(response.content)
#     df = issDf[['latitude','longitude']]
    df.columns = ['altitude', 'daynum', 'footprint', 'id', 'lat', 'lon',
    'name', 'solar_lat', 'solar_lon', 'timestamp', 'units', 'velocity',
    'visibility']
    return df

def projectDf(df, userLat, height):

    #Get projected chart space X's and Y's from the projection func which adds them to the dataframe
    df = df.apply(eqAzProjection,args=(userLat,height),axis=1)

    #add bearing to next point in df
    bearingToNext = 0
    for i in range(0, len(df)):
        if int(i) < len(df)-1:
            x1 = df.loc[i]['x']
            x2 = df.loc[i+1]['x']
            y1 = df.loc[i]['y']
            y2 = df.loc[i+1]['y']
            deltaX = x2-x1
            deltaY = y2-y1
            #bokeh angle takes radians, triangle point is 60 degs (1.0472 rads) offset from 0
            rads = math.atan2(deltaY, deltaX)-1.5708
            df.at[i,'bearingToNext'] = rads
            bearingToNext = rads
        else:      
            df.at[i,'bearingToNext'] = bearingToNext#bearingToNext+ df.iloc[i-1]['bearingToNext']-df.iloc[i-2]['bearingToNext']

    #check to see if coordinate overruns boundary of chart and set to NaN
    #so the ISS path won't bleed over into the chart beside it. 
    if userLat >= 0:
        df.loc[df.eval('x<=500'), 'keepx'] = df.x
        df.loc[df.eval('x<=500'), 'keepy'] = df.y
    else:
        df.loc[df.eval('x >=-500'), 'keepx'] = df.x
        df.loc[df.eval('x>=-500'),'keepy'] = df.y
    df['x'] = df['keepx']
    df['y'] = df['keepy']
    df.drop(['keepx', 'keepy'], axis=1)
    # df.drop(['keepy'],axis=1)    
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
    s['x'] = (k*math.cos(radLat)*(math.sin(radLon-lZero)))*(height/1.67)
    s['y'] = (k*(math.cos(t1)*math.sin(radLat)-math.sin(t1)*math.cos(radLat)*math.cos(radLon-lZero)))*(height/1.67)
    s['x_raw'] = (k*math.cos(radLat)*(math.sin(radLon-lZero)))
    s['y_raw'] = (k*(math.cos(t1)*math.sin(radLat)-math.sin(t1)*math.cos(radLat)*math.cos(radLon-lZero)))
    return s

def getDay(userLat, height):
    dayOfYear = float(datetime.utcnow().timetuple().tm_yday)
    sunList = getSunList(userLat,height)
    subset = sunList[['x', 'y']]
    subset[:]['x']=subset[:]['x']+250
    subset[:]['y']=subset[:]['y']+250

    tuples = [tuple(x) for x in subset.values]

    imFilter = Image.new('RGBA', (500, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(imFilter)
    draw.polygon(tuples, fill=(0,150,100))

    imFilter = imFilter.filter(ImageFilter.GaussianBlur(10))
    if userLat >= 0:
        imFilter.transpose(Image.FLIP_TOP_BOTTOM)
    else:
        imFilter.transpose(Image.FLIP_LEFT_RIGHT)
    imFilterArray = np.array(imFilter)


    # read image as RGB and add alpha (transparency)
    if userLat >=0:
        #GOOD FOR SUMMER N-HEM
        im = Image.open('Images/north_day.png').transpose(Image.FLIP_TOP_BOTTOM)#.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)    
    else:
        #GOOD FOR WINTER S-HEM
        im = Image.open('Images/south_day.png').transpose(Image.FLIP_TOP_BOTTOM)#.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)

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
    if userLat >= 0:
        if dayOfYear <=78 or dayOfYear >=266:
            #winter northern-hemisphere
            newImArray[:,:,3] = 255-imFilterArray[:,:,3]
        else:
            #summer southern-hemisphere
            newImArray[:,:,3] = imFilterArray[:,:,3]
    else:
        if dayOfYear >=78 and dayOfYear <=266:
            #winter southern-hemisphere
            newImArray[:,:,3] = 255-imFilterArray[:,:,3]
        else:
            #summer southern-hemisphere
            newImArray[:,:,3] = imFilterArray[:,:,3]


    newIm = Image.fromarray(newImArray, "RGBA")
    # back to Image from numpy
    finalImArray = np.array(newIm)
    return finalImArray

def getNight(userLat):
    if userLat >= 0:
        im = Image.open('Images/north_night.png').transpose(Image.FLIP_TOP_BOTTOM)
    else:
        im = Image.open('Images/south_night.png').transpose(Image.FLIP_TOP_BOTTOM)
    imArray = np.array(im)
    return imArray

def getCorners():
    im = Image.open('Images/corners.png')#.convert('RGBA')
    imArray = np.array(im)
    return imArray

def getISS():
    im = Image.open('Images/iss.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
    imArray = np.array(im)
    return imArray

def getHubbleIcon():
    im = Image.open('Images/hubble.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
    imArray = np.array(im)
    return imArray

def getUSA224Icon():
    im = Image.open('Images/usa_224.png').convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
    imArray = np.array(im)
    return imArray

def getMoon():
    now = datetime.now()
    now.year
    tau = 2.0 * ephem.pi

    sun = ephem.Sun()
    moon = ephem.Moon()
    names = ['New', 'Waxing Crescent','First Quarter' ,'Waxing Gibbous','Full','Waning Gibbous','Third Quarter', 'Waning Crescent']
    #for n in range(1, 31):
    s = '{}/{}/{}'.format(now.year, now.month, now.day)# n)
    sun.compute(s)
    moon.compute(s)

    sunlon = ephem.Ecliptic(sun).lon
    moonlon = ephem.Ecliptic(moon).lon

    angle = (moonlon - sunlon) % tau
    deg = round(float(math.degrees(angle)))
    quarterIdx = int(angle * 8.0 // tau)

    # if 175.0 <= deg <= 185.0:
    #     quarterName = 'Full'
    # elif deg>= 355.0 or deg <=5.0:
    #     quarterName = 'New'
    # else:
    quarterName = names[quarterIdx]

    if quarterName == 'New':
        im = Image.open('Images/moon_new.png').transpose(Image.FLIP_TOP_BOTTOM) 
    elif quarterName == 'Waxing Crescent':
        im = Image.open('Images/moon_waxing_crescent.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'First Quarter':
        im = Image.open('Images/moon_waxing_gibbous.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'Waxing Gibbous':
        im = Image.open('Images/moon_waxing_gibbous.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'Full':
        im = Image.open('Images/moon_full.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'Waning Gibbous':
        im = Image.open('Images/moon_waning_gibbous.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'Third Quarter':
        im = Image.open('Images/moon_waning_gibbous.png').transpose(Image.FLIP_TOP_BOTTOM)
    elif quarterName == 'Waning Crescent':
        im = Image.open('Images/moon_waning_crescent.png').transpose(Image.FLIP_TOP_BOTTOM)
    imArray = np.array(im)
    return imArray

def getN2Y0sat(satId, n2yokey):
    url="https://www.n2yo.com/rest/v1/satellite/positions/"+str(satId)+"/0/0/0/1000&apiKey="+str(n2yokey)
    response = requests.get(url)
    if response:
        satName = json.loads(response.content.decode("utf-8"))['info']['satname']
        df = pd.DataFrame(json.loads(response.content.decode("utf-8"))['positions'])[['satlatitude', 'satlongitude']]
        df['satName']= satName
    df.columns= ['lat', 'lon', 'satName']
    return df

def plotSat(figure, imageHeight, color, pathDf, satLoc, directionalArrowSize, circleSize, iconImage, iconSize, iconAlpha=0.9, lineAlpha=0.9):
    figure.line(pathDf.x-imageHeight, pathDf.y, color=color, line_width = 1)# line_dash=[10,5], line_width=3)
    if not np.isnan(pathDf.loc[satLoc]['x']):
        figure.triangle(pathDf.x-imageHeight
                , pathDf.y
                , color=color
                , size = directionalArrowSize
                , alpha = lineAlpha
                , angle = pathDf.bearingToNext)
        figure.circle(pathDf.loc[satLoc]['x']-imageHeight, pathDf.loc[satLoc]['y'], color=color, size=circleSize, alpha = iconAlpha)
        figure.image_rgba(image=[iconImage], x=pathDf.loc[satLoc]['x']-imageHeight-(iconSize/2), y = pathDf.loc[satLoc]['y']-(iconSize/2), dh =iconSize, dw=iconSize)

def getChart(n2yokey=None, adhoc=None):
    userLat = 35 
    height = 500
    width = height*2
    issIndex = 6
    issDf = getISSList()
    northISSdf = projectDf(issDf, userLat, height)
    southISSdf = projectDf(issDf, -userLat,height)

    northDay = getDay(userLat,height)
    southDay = getDay(-userLat,height)
    northNight = getNight(userLat)
    southNight = getNight(-userLat)
    corners = getCorners()
    iss = getISS()
    hubble = getHubbleIcon()
    usa224 = getUSA224Icon()
    moonDf = getMoonList()
    northMoonDf = projectDf(moonDf, userLat, height).dropna().reset_index()
    southMoonDf = projectDf(moonDf, -userLat, height).dropna().reset_index()
    northMoon = getMoonLocation(userLat, height)
    southMoon = getMoonLocation(-userLat, height)
    moon = getMoon()
    footprint = int(2*math.sqrt(((issDf.loc[issIndex]['footprint']*width)/height)/math.pi))

    if not np.isnan(northISSdf.loc[issIndex]['x']):
        text = 'Lat:'+str(round(northISSdf.loc[issIndex]['lat'],2))\
                +' Lon:'+str(round(northISSdf.loc[issIndex]['lon'],2))\
                +'\r\nAltitude:'+str(round(northISSdf.loc[issIndex]['altitude'],2))+' '+str(northISSdf.loc[5]['units'])\
                +'\r\nSpeed:'+str(round(northISSdf.loc[issIndex]['velocity'],2))+' '+str(northISSdf.loc[5]['units']+' per hour')
    elif not np.isnan(southISSdf.loc[issIndex]['x']):
        text = 'Lat:'+str(round(southISSdf.loc[issIndex]['lat'],2))\
            +' Lon:'+str(round(southISSdf.loc[issIndex]['lon'],2))\
            +'\r\nAltitude:'+str(round(southISSdf.loc[issIndex]['altitude'],2))+' '+str(southISSdf.loc[5]['units'])\
            +'\r\nSpeed:'+str(round(southISSdf.loc[issIndex]['velocity'],2))+' '+str(southISSdf.loc[5]['units']+' per hour')
    else:
        text = ''

    c = figure(width = width, height = height, x_range =(-width, width), y_range=(-height,height))
    c.title.text = text
    c.title.align = "center"
    c.title.text_color = "white"
    c.title.text_font_size = "12px"
    c.title.background_fill_color = "black"

    ###NORTHERN HEMISPHERE
    c.image_rgba(image=[northNight], x =-width, y=-height, dh =width, dw=width)
    c.image_rgba(image=[northDay], x =-width, y=-height, dh =width, dw=width)

    ###SOUTHERN HEMISPHERE
    c.image_rgba(image=[southNight], x =0, y=-height, dh =width, dw=width)
    c.image_rgba(image=[southDay], x =0, y=-height, dh =width, dw=width)
    
    ###SATELLITES
    #ADHOC SAT NORTH AND SOUTH
    #ADHOC SATS i.e. NOAA19: 33591 ; GOES 15: 36411 ; LANDSAT 8: 39084; 
    adhocSat = adhoc
    if n2yokey and adhocSat:
        adHocNames =[]
        colorsAdhoc = viridis(len(adhocSat)*2)
        if len(adhocSat)>0:
            for num, sat in enumerate(adhocSat, start = 0):
                colorIndex = num*2
                adf = getN2Y0sat(sat, n2yokey )
                adf = adf[adf.index%100 == 0].reset_index()
                northAdf = projectDf(adf, userLat, height)
                southAdf = projectDf(adf, -userLat, height)
                
                adHocNames.append(northAdf.loc[0]['satName'])
                plotSat(c, height, colorsAdhoc[colorIndex], northAdf, 0, 8, 25, hubble, 40)
                plotSat(c, -height, colorsAdhoc[colorIndex], southAdf, 0, 8, 25, hubble, 40)
                
    #ISS NORTH   
    plotSat(c, height, "purple", northISSdf, issIndex, 10, footprint, iss, 80, 0.5, 0.8)

    #MOON NORTH
    # c.line(northMoonDf.x-height, northMoonDf.y, color="white", line_dash=[5,15], line_width=1, line_alpha = 0.6)
    c.triangle(northMoonDf.x-height
        , northMoonDf.y
        , color="white"
        , size = 5
        , alpha = 0.2
        , angle = northMoonDf.bearingToNext - 1.5708 )
    if not np.isnan(northMoon.loc[0]['x']) and northMoon.loc[0]['x']<500:    
        c.image_rgba(image=[moon], x=northMoon.loc[0]['x']-height-75, y = northMoon.loc[0]['y']-75, dh =150, dw=150)

    c.image_rgba(image=[corners], x =-width, y=-height, dh =width, dw=width)
    
    #ISS SOUTH
    plotSat(c, -height, "purple", southISSdf, issIndex, 10, footprint, iss, 80, 0.5, 0.8)

    #MOON SOUTH
    # c.line(southMoonDf.x+height, southMoonDf.y, color="white", line_width=1, line_alpha = 0.6)#, line_dash=[5,15])    
    c.triangle(southMoonDf.x+height
        , southMoonDf.y
        , color="white"
        , size = 5
        , alpha = 0.2
        , angle = southMoonDf.bearingToNext - 1.5708 )
    if not np.isnan(southMoon.loc[0]['x']):
        c.image_rgba(image=[moon], x=southMoon.loc[0]['x']+height-75, y = southMoon.loc[0]['y']-75, dh =150, dw=150)

    c.image_rgba(image=[corners], x =0, y=-height, dh =width, dw=width)
    c.background_fill_color = "#000000"
    c.toolbar_location = None
    c.axis.visible = False
    c.border_fill_color = '#000000'
    c.outline_line_color = None

    #LEGEND
    c.circle(-960, 457, size=35, alpha = 0.5, color="purple")
    c.image_rgba(image=[iss], x=-997, y = 415, dh =80, dw=80)
    issLabel = Label(text = 'ISS', x = -910, y = 435, text_color = 'white', text_font_size = "10pt")
    c.add_layout(issLabel)

    if n2yokey and adhocSat:
        colorsAdhoc = viridis(len(adhocSat))
        if len(adhocSat)>0:
            for num, sat in enumerate(adhocSat, start = 0):
                colorIndex = num
                y = 455 #-num*70
                x = -830 + (num*170)
                circle = c.circle(x+20, y, color = colorsAdhoc[colorIndex], size=25, alpha = 0.9)
                image = c.image_rgba(image=[hubble], x= x, y = y-20, dh =40, dw=40)
                adHocLabel = Label(text = adHocNames[num], x = x+55, y = y-15, text_color = 'white', text_font_size = "8pt")
                c.add_layout(adHocLabel)


    # print (northMoon, southMoon)
    # output_notebook(hide_banner=True)
    # show(c)
    # end = datetime.now()-start
    # print(end, 'vs 2.78 seconds')
    return c