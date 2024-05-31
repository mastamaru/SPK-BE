from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import pandas as pd
import os


mongo_uri = os.environ['MONGO_URI']

client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = client['SPK']
df = pd.read_csv('./data/anime.csv')


app = Flask(__name__)
CORS(app)

@app.route('/db', methods=['GET'])
def get_db():
    search_query = request.args.get('search', '')
    results = []

    if search_query:
        query = {"title": {"$regex": search_query, "$options": "i"}}
        for item in db.anime_meta.find(query):
            results.append({
                "title": item['title'],
                "type": item.get('type', ''),
                "episodes": item.get('episodes', ''),
                "score": item.get('score', ''),
                "aired_from": item.get('aired_from', ''),
                "aired_to": item.get('aired_to', ''),
                "synopsis": item.get('synopsis', ''),
                "genre": item.get('genre', []),
                "poster": item.get('poster', ''),
                "streaming_link": item.get('streaming_link', '')
            })
    else:
        for item in db.anime_meta.find():
            results.append(item['title'])

    return jsonify(results)

@app.route('/', methods=['GET'])
def home():
    return "<h1>API is working</h1>"
# get anime titles
@app.route('/anime', methods=['GET'])
def get_anime():
    titles = df['name'].values
    sort_titles = sorted(titles)
    sort_titles = sort_titles[95:]
    return jsonify(sort_titles)