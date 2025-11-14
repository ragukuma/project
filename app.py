from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import csv
import os

app = Flask(__name__)
CORS(app)

CSV_FILE = os.getenv('CSV_FILE', 'reviews.csv')


def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'email', 'phone', 'rating', 'review', 'created_at'])

init_csv()

def get_next_id():
    try:
        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            if not rows:
                return 1
            return int(rows[-1]['id']) + 1
    except:
        return 1

@app.route('/api/reviews', methods=['POST'])
def add_review():
    try:
        data = request.json
        next_id = get_next_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        review_data = {
            'id': next_id,
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'gender': data['gender'],
            'rating': data['rating'],
            'review': data['review'],
            'created_at': current_time
        }
        
        # Check if file is empty (only header exists)
        file_empty = os.path.getsize(CSV_FILE) == 0
        
        with open(CSV_FILE, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=['id', 'name', 'email', 'phone', 'gender','rating', 'review', 'created_at'])
            if file_empty:
                writer.writeheader()
            writer.writerow(review_data)
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        limit = request.args.get('limit', default=5, type=int)
        
        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            # Convert to list and sort by created_at in reverse order
            reviews = list(reader)
            reviews.sort(key=lambda x: x['created_at'], reverse=True)
            # Return only the requested number of reviews
            return jsonify(reviews[:limit])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True, port=5000)