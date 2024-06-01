from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import pandas as pd
import os
from sklearn.metrics.pairwise import cosine_similarity
import hashlib

mongo_uri = os.environ['MONGO_URI']

client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = client['SPK']
df = pd.read_csv('./data/anime.csv')

df_meta = pd.read_csv('db_processed.csv')

app = Flask(__name__)
CORS(app)


def hash_password(password):
    salt = os.urandom(16)  # Membuat salt acak
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt + hash_obj


def verify_password(stored_password, provided_password):
    salt = stored_password[:16]  # Ambil 16 byte pertama sebagai salt
    stored_hash = stored_password[16:]
    hash_obj = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt, 100000)
    return stored_hash == hash_obj


def get_recommendations(title, cosine_sim, df_anime):
    # Mengecek apakah judul ada dalam indeks
    if title not in df_anime.index:
        return f"Anime dengan judul '{title}' tidak ditemukan."

    # Mendapatkan indeks dari anime yang dicari
    idx = df_anime.index.get_loc(title)

    # Mendapatkan skor similarity dari semua anime dengan anime yang dicari
    sim_scores = list(enumerate(cosine_sim[idx]))

    # Mengurutkan anime berdasarkan similarity score
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Mendapatkan 10 anime teratas yang paling mirip
    sim_scores = sim_scores[1:]

    # Mendapatkan nama anime dan skor similarity dari indeks
    anime_indices = [i[0] for i in sim_scores]
    similarity_scores = [i[1] for i in sim_scores]

    # Menggabungkan nama anime dan skor similarity dalam satu DataFrame
    recommendations = pd.DataFrame({
        'Anime': df_anime.iloc[anime_indices].index,
    })

    return recommendations


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


@app.route('/register', methods=['POST'])
def register():
    # get data from request, with format json 'username' and 'password'
    data = request.get_json()
    name = data['name']
    username = data['username']
    password = data['password']

    anime = data['anime']

    df_anime = df[df['name'] == anime]
    # check if user already registered
    if db.user_data.find_one({'username': username}):
        return jsonify({'message': 'User already registered'})

    df_anime['episodes'] = df_anime['episodes'].astype(int)
    df_anime['genre'] = df_anime['genre'].apply(lambda x: x.split(', '))
    for index, row in df_anime.iterrows():
        for genre in row['genre']:
            df_anime.at[index, genre] = 1

    df_anime.fillna(0, inplace=True)

    anime_length = ['Short', 'Medium', 'Long']

    df_anime['episodes'] = pd.cut(df_anime['episodes'], bins=[0, 12, 26, 2000], labels=anime_length)

    for length in anime_length:
        df_anime['episode' + length] = df_anime['episodes'].apply(lambda x: 1 if x == length else 0)

    df_anime.drop('episodes', axis=1, inplace=True)

    for t in df_anime['type'].unique():
        df_anime[t] = df_anime['type'].apply(lambda x: 1 if x == t else 0)

    df_anime.drop('type', axis=1, inplace=True)
    df_anime.drop(['genre'], axis=1, inplace=True)

    user_rec = pd.concat([df_meta, df_anime], axis=0)
    user_rec.fillna(0, inplace=True)
    user_rec.set_index('name', inplace=True)

    cosine_sim = cosine_similarity(user_rec, user_rec)

    hashed_password = hash_password(password)
    recommendations = get_recommendations(anime, cosine_sim, user_rec)
    # testing recommendation
    # return jsonify({'message': f'here are the recommendation : {get_recommendations(anime, cosine_sim, user_rec)} for user {username}'})

    # insert user data and recommendations to database
    db.user_data.insert_one({
        'name': name,
        'username': username,
        'password': hashed_password,
        'recommendations': recommendations['Anime'].tolist()
    })

    return jsonify({'message': f"User {username} registered with recommendations: {recommendations}"})


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    user = db.user_data.find_one({'username': username})
    if user and verify_password(user['password'], password):
        return jsonify({'message': f"User {username} logged in with recommendations: {user['recommendations']}"})
    else:
        return jsonify({'message': 'Invalid username or password'})
    
    
@app.route('/get_name', methods=['GET'])
def get_name():
    username = request.args.get('username')
    user = db.user_data.find_one({'username': username})
    if user:
        return jsonify({'name': user['name']})
    else:
        return jsonify({'message': 'User not found'})


@app.route('/fetch_anime', methods=['GET'])
def fetch_anime():
    username = request.args.get('username')
    user = db.user_data.find_one({'username': username})
    if user:
        anime = user['recommendations']
        results = []
        for title in anime:
            query = {"title": title}
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
        return jsonify(results)
    else:
        return jsonify({'message': 'User not found'})
