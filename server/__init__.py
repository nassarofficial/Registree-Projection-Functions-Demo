from flask import Flask, render_template, request, redirect, url_for, \
	jsonify, session  # For flask implementation
from pymongo import MongoClient  # Database connector
import json
import os
import math
import requests
import configparser

config = configparser.ConfigParser()                                     
config.read('server/config.ini')

cl = \
	MongoClient(config.get('PARAMS', 'MONOGO_URL'))

db = cl.la

mapillary_client_id = config.get('PARAMS', 'MAPILLARY_KEY')

app = Flask(__name__)

app.secret_key = config.get('PARAMS', 'APP_SECRET_KEY')

GOOGLE_API_URL = config.get('PARAMS', 'GOOGLE_API_URL')

port = int(os.getenv('PORT', config.get('PARAMS', 'PORT')))

EARTH_RADIUS = 6371000
GOOGLE_CAR_CAMERA_HEIGHT = 3


def haversine_distance(
	lat1,
	lon1,
	lat2,
	lon2,
	):
	a = math.sin(math.radians((lat2 - lat1) / 2.0)) ** 2 \
		+ math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) \
		* math.sin(math.radians((lon2 - lon1) / 2.0)) ** 2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	return EARTH_RADIUS * c


def crawl_all_panos(latitude, longitude, radius):
	response = \
	requests.get("https://a.mapillary.com/v3/images?client_id="+mapillary_client_id+"&closeto=" \
    + str(longitude)+","+str(latitude)+"&lookat="+str(longitude)+","+str(latitude)+"&pano=true")

	if response.status_code == 200:
	    response_feats = response.json()["features"]
	    response_feats.sort(key=lambda k: haversine_distance(latitude, longitude, k['geometry']['coordinates'][1], k['geometry']['coordinates'][0]))
	    response_feats = response_feats[:4]
	else:
		response_feats = response
	return response_feats


@app.route('/', methods=['GET', 'POST'])
def get_load_marker():
	select = "la"
	cols = db[select].find()
	session['dataset'] = select
	data = []
	for document in cols:
		tmp = str(document['_id'])
		del document['_id']
		document['_id'] = tmp
		data.append(document)
		break
	return render_template('index.html', h='RegisTree Demo | Projection Function'
						   , data=data, center={"status":"None"}, g_api=GOOGLE_API_URL)


@app.route('/get_panos', methods=['GET', 'POST'])
def get_panos():
	data = request.json
	lat = data["lat"]
	lng = data["lng"]
	panos = crawl_all_panos(float(lat), float(lng), 100)
	return jsonify(
        response = panos)


@app.route('/GetBoundsMarkers', methods=['GET', 'POST'])
def getboundsmarkers():
	try:
		docs = []
		select = session['dataset']
		cols = db[select]
		data = request.json
		minval = 0
		classval = data["minselect"]
		if data["minselect"] == "All":
			minval = 0
		else:
			minval = float(data["minselect"])
		if data["maxselect"] == "All":
			maxval = 500
		else:
			maxval = float(data["maxselect"])
		if data["class"] == "All":
			classval = ".*?"
		else:
			classval = ".*"+data["class"]+".*"

		bound_data = cols.find({"$and":[{
			     'location': {
			       '$geoWithin': {
			          '$geometry': {
			             'type' : 'Polygon' ,
			             'coordinates': [[ 
			                        [ data['west'], data['north'] ], 
			                        [ data['west'], data['south'] ], 
			                        [ data['east'], data['south'] ],              
			                        [ data['east'], data['north'] ],
			                        [ data['west'], data['north'] ]
			                           ]]
			       }
			     }
			   }
			},{ "diameter": { "$gt": minval, "$lt": maxval } },{"class": {"$regex" : classval}}]})
		for document in bound_data:
			tmp = str(document['_id'])
			del document['_id']
			document['_id'] = tmp
			docs.append(document)

		d = docs
	except:
		d = "failed"
	return jsonify(
        response = d)


if 'FLASK_LIVE_RELOAD' in os.environ and os.environ['FLASK_LIVE_RELOAD'] == 'true':
	import livereload
	app.debug = False
	server = livereload.Server(app.wsgi_app)
	server.serve(port=os.environ['port'], host=os.environ['host'])
