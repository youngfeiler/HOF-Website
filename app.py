
from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO
import plotly as plotly
from functionality.database import database
import pandas as pd
import os
import stripe
import time
import atexit
from functionality.db_manager import DBManager
import warnings
warnings.filterwarnings("ignore")
from flask_socketio import SocketIO
import jsonpickle
from flask import Flask, jsonify
from flask_socketio import SocketIO
import time
import pandas as pd
import flock as flock
from flask_cors import CORS
import redis
import psutil
from functools import wraps
import simplejson as json
from decimal import Decimal


process = psutil.Process(os.getpid())

redis_client = redis.Redis(host='localhost', port=6379, db=0)

from flask_compress import Compress
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def create_app():
    app = Flask(__name__, template_folder='static/templates', static_folder='static')
    CORS(app, supports_credentials=False, resources={r"/*": {"origins": "*"}})



    Compress(app)
    # TODO: Put this key in the secret file
    app.secret_key = 'to_the_moon'
    app.db_manager = DBManager()
    app.db = database(app.db_manager)

    from functionality.routes.api import api
    app.register_blueprint(api)

    return app


app = create_app()
app.config['REACT_COMPONENT_DIRECTORY'] = os.path.join(app.root_path, 'react_frontend')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None'
)

socketio = SocketIO(app)


def read_cached_df(path):
    serialized_df = redis_client.get(path)
    if serialized_df:
      serialized_df = serialized_df.decode('utf-8')
      cached_df = pd.read_json(serialized_df)
      return cached_df
    else:
      raise FileNotFoundError(f"No cached DataFrame found at path: {path}")


@app.route('/api/login_status')
def login_status():
    is_logged_in = True if 'user_id' in session else False
    return jsonify({"login_status": is_logged_in})


app.config['STRIPE_PUBLIC_KEY'] = 'pk_live_51Nm0vBHM5Jv8uc5M5hu3bxlKg6soYb2v9xSg5O7a9sXi6JQJpl7nPWiNKrNHGlXf5g8PFnN6sn0wcLOrixvxF8VH00nVoyGtCk'

app.config['STRIPE_PRIVATE_KEY'] = password = os.environ.get("STRIPE_API_KEY")

stripe.api_key = app.config['STRIPE_PRIVATE_KEY']

@atexit.register
def close_db():
    app.db_manager.close()



   

def retry_on_session_error(max_retries=3, delay=1):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except KeyError as e:
                    if 'user_id' in str(e) and attempt < max_retries - 1:
                        logger.warning(f"user_id not found in session. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator




@app.route('/api/get_MMA_Data', methods=['GET'])
def get_MMA_data():
    # Check if data is cached in Redis
    cache_key = "mma_data"
    cached_data = redis_client.get(cache_key)

    if cached_data:
        # Decode the cached data to check if it's empty
        decoded_data = jsonpickle.decode(cached_data)
        
        # If cached data is found but empty, delete the cache and query the database
        if not decoded_data:  # Assuming an empty list or dataframe in the cache
            logger.info('Empty cached data, clearing cache')
            redis_client.delete(cache_key)
        else:
            logger.info('here is the cached data')
            return jsonify(decoded_data)

    # If not cached or the cache was empty, query the database
    event_data = app.db.get_mma_data()
    logger.info('here is the data from the db')
    # Store the result in Redis with a timeout (e.g., 1 hour = 3600 seconds)
    redis_client.set(cache_key, jsonpickle.encode(event_data), ex=700)

    return jsonify(event_data)



@app.route('/api/get_MMA_Game_Data', methods=['GET'])
def get_MMA_Game_Data():
    game_id = request.args.get('gameId')
    cache_key = f"mma_game_data:{game_id}"
    
    # Check if game data is cached
    cached_data = redis_client.get(cache_key)
    logger.info('start of mma_game_data request')

    if cached_data:
        logger.info('Cached data returned')
        # Return cached data if available
        return jsonify(jsonpickle.decode(cached_data))

    # Otherwise, query the database
    logger.info('start of mma_game_data db rq')
    game_data = app.db.get_MMA_game_data(game_id)
    logger.info('end of mma_game_data db rq')

    # Store the result in Redis with a timeout
    redis_client.set(cache_key, jsonpickle.encode(game_data), ex=700)
    logger.info('set cache')

    return jsonify(game_data)


# @app.route('/api/get_MMA_Data', methods=['GET'])
# def get_MMA_data():
#     event_data = app.db.get_mma_data()
#     return jsonify(event_data)


# @app.route('/api/get_MMA_Game_Data', methods = ['GET'])
# def get_MMA_Game_Data():
#     game_id = request.args.get('gameId')
#     game_data = app.db.get_MMA_game_data(game_id)
#     logger.info('Game data')
#     logger.info(game_data)
#     return jsonify(game_data)



if __name__ == '__main__':

    socketio.run(app, debug=True, port=5000, use_reloader=False)