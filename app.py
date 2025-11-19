from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import mysql.connector
from mysql.connector import pooling
import os

app = Flask(__name__)
CORS(app)

# Database configuration from environment variables
db_config = {
    "host": os.getenv("DB_HOST", "srv2108.hstgr.io"),
    "user": os.getenv("DB_USER", "u772270336_arvels"),
    "password": os.getenv("DB_PASSWORD", "Arvels123"),
    "database": os.getenv("DB_NAME", "u772270336_arvels"),
    "port": int(os.getenv("DB_PORT", "3306"))
}

# Create connection pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name="review_pool",
    pool_size=5,
    pool_reset_session=True,
    **db_config
)

def init_database():
    """Initialize database and create table if not exists"""
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                gender VARCHAR(20),
                rating INT NOT NULL,
                review TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_created_at (created_at)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Initialize database on startup
init_database()

@app.route('/api/reviews', methods=['POST'])
def add_review():
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'rating', 'review']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400
        
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        # Gender is optional
        gender = data.get('gender', 'Not specified')
        
        query = """
            INSERT INTO reviews (name, email, phone, gender, rating, review)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            data['name'],
            data['email'],
            data['phone'],
            gender,
            int(data['rating']),
            data['review']
        )
        
        cursor.execute(query, values)
        conn.commit()
        
        review_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "id": review_id,
            "message": "Review added successfully"
        }), 201
        
    except mysql.connector.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        limit = request.args.get('limit', default=5, type=int)
        
        # Validate limit
        if limit < 1 or limit > 100:
            return jsonify({"status": "error", "message": "Limit must be between 1 and 100"}), 400
        
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT id, name, email, phone, gender, rating, review, created_at
            FROM reviews
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        reviews = cursor.fetchall()
        
        # Convert datetime to string for JSON serialization
        for review in reviews:
            if review['created_at']:
                review['created_at'] = review['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify(reviews), 200
        
    except mysql.connector.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/reviews/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    """Delete a review by ID"""
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM reviews WHERE id = %s"
        cursor.execute(query, (review_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Review not found"}), 404
        
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Review deleted"}), 200
        
    except mysql.connector.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about reviews"""
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Total reviews
        cursor.execute("SELECT COUNT(*) as total FROM reviews")
        total = cursor.fetchone()['total']
        
        # Average rating
        cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews")
        avg_rating = cursor.fetchone()['avg_rating'] or 0
        
        # Rating distribution
        cursor.execute("""
            SELECT rating, COUNT(*) as count 
            FROM reviews 
            GROUP BY rating
        """)
        distribution = cursor.fetchall()
        
        rating_dist = {
            '5_star': 0,
            '4_star': 0,
            '3_star': 0,
            '2_star': 0,
            '1_star': 0
        }
        
        for item in distribution:
            rating_dist[f"{item['rating']}_star"] = item['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "total_reviews": total,
            "average_rating": float(avg_rating),
            "rating_distribution": rating_dist
        }), 200
        
    except mysql.connector.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host="0.0.0.0", debug=False, port=port)
