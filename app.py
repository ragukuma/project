from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import mysql.connector
from mysql.connector import pooling
import os
import traceback

app = Flask(__name__)
CORS(app)

# Database configuration from environment variables
db_config = {
    "host": os.getenv("DB_HOST", "srv2108.hstgr.io"),
    "user": os.getenv("DB_USER", "u772270336_arvels"),
    "password": os.getenv("DB_PASSWORD", "Arvels123"),
    "database": os.getenv("DB_NAME", "u772270336_arvels"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "autocommit": False
}

# Create connection pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name="review_pool",
    pool_size=5,
    pool_reset_session=True,
    **db_configM
)

def get_connection():
    """Get a connection from pool with proper configuration"""
    try:
        conn = connection_pool.get_connection()
        conn.autocommit = False
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Error getting connection: {err}")
        raise

def init_database():
    """Initialize database and create table if not exists"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                gender VARCHAR(20),
                rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
                review TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_created_at (created_at DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        conn.commit()
        print("✅ Database initialized successfully")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Initialize database on startup
init_database()

@app.route('/')
def home():
    """Root endpoint"""
    return jsonify({
        "message": "Review API Server",
        "status": "running",
        "endpoints": {
            "POST /api/reviews": "Add a new review",
            "GET /api/reviews": "Get all reviews",
            "DELETE /api/reviews/<id>": "Delete a review",
            "GET /api/stats": "Get review statistics",
            "GET /api/health": "Health check",
            "GET /api/test-connection": "Test database connection",
            "GET /api/raw-connection-test": "Raw connection test"
        }
    }), 200

@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Add a new review"""
    conn = None
    cursor = None
    try:
        data = request.json
        print(f"📝 Received review data: {data}")
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'rating', 'review']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                print(f"❌ Missing field: {field}")
                return jsonify({
                    "status": "error", 
                    "message": f"Missing or empty field: {field}"
                }), 400
        
        # Validate rating
        rating = int(data['rating'])
        if rating < 1 or rating > 5:
            return jsonify({
                "status": "error", 
                "message": "Rating must be between 1 and 5"
            }), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        gender = data.get('gender', 'Not specified')
        
        query = """
            INSERT INTO reviews (name, email, phone, gender, rating, review, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        values = (
            data['name'].strip(),
            data['email'].strip(),
            data['phone'].strip(),
            gender,
            rating,
            data['review'].strip()
        )
        
        cursor.execute(query, values)
        review_id = cursor.lastrowid
        conn.commit()
        
        print(f"✅ Review created successfully: ID {review_id}")
        
        return jsonify({
            "status": "success",
            "id": review_id,
            "message": "Review added successfully"
        }), 201
        
    except mysql.connector.Error as e:
        print(f"❌ Database error in add_review: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        return jsonify({
            "status": "error", 
            "message": "Invalid rating value"
        }), 400
    except Exception as e:
        print(f"❌ Unexpected error in add_review: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    """Get all reviews"""
    conn = None
    cursor = None
    try:
        limit = request.args.get('limit', default=50, type=int)
        
        if limit < 1 or limit > 100:
            return jsonify({
                "status": "error", 
                "message": "Limit must be between 1 and 100"
            }), 400
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        
        query = """
            SELECT id, name, email, phone, gender, rating, review, created_at
            FROM reviews
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        reviews = cursor.fetchall()
        
        print(f"✅ Fetched {len(reviews)} reviews from database")
        
        # Convert datetime to string
        for review in reviews:
            if review['created_at']:
                review['created_at'] = review['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(reviews), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error in get_reviews: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    except Exception as e:
        print(f"❌ Unexpected error in get_reviews: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/reviews/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    """Delete a review by ID"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM reviews WHERE id = %s"
        cursor.execute(query, (review_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            print(f"⚠️ Review {review_id} not found")
            return jsonify({
                "status": "error", 
                "message": "Review not found"
            }), 404
        
        print(f"✅ Review {review_id} deleted successfully")
        
        return jsonify({
            "status": "success", 
            "message": "Review deleted"
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error in delete_review: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    except Exception as e:
        print(f"❌ Unexpected error in delete_review: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get review statistics"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM reviews")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews")
        avg_rating = cursor.fetchone()['avg_rating'] or 0
        
        cursor.execute("""
            SELECT rating, COUNT(*) as count 
            FROM reviews 
            GROUP BY rating
            ORDER BY rating DESC
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
        
        print(f"✅ Stats - Total: {total}, Avg Rating: {avg_rating:.2f}")
        
        return jsonify({
            "total_reviews": total,
            "average_rating": round(float(avg_rating), 2),
            "rating_distribution": rating_dist
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error in get_stats: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    except Exception as e:
        print(f"❌ Unexpected error in get_stats: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM reviews")
        count = cursor.fetchone()[0]
        
        print(f"✅ Health check passed - {count} reviews in database")
        
        return jsonify({
            "status": "healthy", 
            "database": "connected",
            "total_reviews": count
        }), 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return jsonify({
            "status": "unhealthy", 
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """Detailed connection test"""
    results = {}
    conn = None
    cursor = None
    
    try:
        results['connection_pool'] = 'OK'
        
        conn = get_connection()
        results['get_connection'] = 'OK'
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        results['execute_query'] = 'OK'
        
        cursor.execute("SHOW TABLES LIKE 'reviews'")
        if cursor.fetchone():
            results['table_exists'] = 'OK'
        else:
            results['table_exists'] = 'FAILED - Table not found'
        
        cursor.execute("SELECT COUNT(*) FROM reviews")
        count = cursor.fetchone()[0]
        results['review_count'] = count
        
        cursor.execute("""
            SELECT id, name, rating, created_at 
            FROM reviews 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        recent = cursor.fetchall()
        results['recent_reviews'] = [
            {
                'id': r[0], 
                'name': r[1], 
                'rating': r[2], 
                'created_at': str(r[3])
            } for r in recent
        ]
        
        print(f"✅ Connection test passed - {count} reviews found")
        
        return jsonify({
            "status": "success",
            "message": "All tests passed",
            "tests": results
        }), 200
        
    except Exception as e:
        results['error'] = str(e)
        print(f"❌ Connection test failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Connection test failed",
            "tests": results
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/raw-connection-test', methods=['GET'])
def raw_connection_test():
    """Raw MySQL connection test with detailed logging"""
    logs = []
    
    try:
        logs.append("=== TESTING RAW MYSQL CONNECTION ===")
        logs.append(f"Step 1: Connecting to {db_config['host']}")
        logs.append(f"Database: {db_config['database']}")
        logs.append(f"User: {db_config['user']}")
        
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=db_config['port']
        )
        logs.append("✅ Raw connection successful!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()[0]
        logs.append(f"✅ Connected to database: {current_db}")
        
        cursor.execute("SHOW TABLES LIKE 'reviews'")
        table_exists = cursor.fetchone()
        if table_exists:
            logs.append("✅ 'reviews' table EXISTS")
        else:
            logs.append("❌ 'reviews' table DOES NOT EXIST!")
            return jsonify({"status": "error", "logs": logs}), 500
        
        logs.append("Step 4: Inserting test review...")
        insert_query = """
            INSERT INTO reviews (name, email, phone, gender, rating, review, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        test_data = ('CONNECTION TEST', 'test@connection.com', '0000000000', 'Test', 5, f'Test at {datetime.now()}')
        cursor.execute(insert_query, test_data)
        inserted_id = cursor.lastrowid
        logs.append(f"✅ INSERT executed, got ID: {inserted_id}")
        
        logs.append("Step 5: Committing...")
        conn.commit()
        logs.append("✅ COMMIT successful")
        
        cursor.execute("SELECT * FROM reviews WHERE id = %s", (inserted_id,))
        found_same = cursor.fetchone()
        if found_same:
            logs.append(f"✅ Found in same connection")
        else:
            logs.append(f"❌ NOT found in same connection!")
        
        cursor.close()
        conn.close()
        
        logs.append("Step 7: Opening NEW connection...")
        conn2 = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=db_config['port']
        )
        cursor2 = conn2.cursor(dictionary=True)
        
        cursor2.execute("SELECT * FROM reviews WHERE id = %s", (inserted_id,))
        found_new = cursor2.fetchone()
        
        if found_new:
            logs.append(f"✅✅✅ SUCCESS! Data persists in NEW connection!")
        else:
            logs.append(f"❌❌❌ FAILED! Data NOT found in new connection!")
        
        cursor2.execute("SELECT COUNT(*) as cnt FROM reviews")
        total = cursor2.fetchone()['cnt']
        logs.append(f"Total reviews in database: {total}")
        
        cursor2.close()
        conn2.close()
        
        return jsonify({
            "status": "success",
            "inserted_id": inserted_id,
            "persisted": found_new is not None,
            "total_reviews": total,
            "logs": logs
        }), 200
        
    except Exception as e:
        logs.append(f"❌ ERROR: {str(e)}")
        logs.append(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "logs": logs
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host="0.0.0.0", debug=False, port=port)
