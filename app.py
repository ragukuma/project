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
    "port": int(os.getenv("DB_PORT", "3306")),
    "autocommit": False  # CRITICAL: Explicit transaction control
}

# Create connection pool with proper settings
connection_pool = pooling.MySQLConnectionPool(
    pool_name="review_pool",
    pool_size=5,
    pool_reset_session=True,
    **db_config
)

def get_connection():
    """Get a connection from pool with proper configuration"""
    try:
        conn = connection_pool.get_connection()
        conn.autocommit = False  # Ensure explicit commits
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

@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Add a new review with guaranteed persistence"""
    conn = None
    cursor = None
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'rating', 'review']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({
                    "status": "error", 
                    "message": f"Missing or empty field: {field}"
                }), 400
        
        # Validate rating range
        rating = int(data['rating'])
        if rating < 1 or rating > 5:
            return jsonify({
                "status": "error", 
                "message": "Rating must be between 1 and 5"
            }), 400
        
        # Get fresh connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Gender is optional
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
        
        # CRITICAL: Explicit commit saves data permanently
        conn.commit()
        
        print(f"✅ Review saved - ID: {review_id}, Name: {data['name']}, Rating: {rating}")
        
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
        # Always close resources
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    """Get reviews with fresh database read"""
    conn = None
    cursor = None
    try:
        limit = request.args.get('limit', default=50, type=int)
        
        # Validate limit
        if limit < 1 or limit > 100:
            return jsonify({
                "status": "error", 
                "message": "Limit must be between 1 and 100"
            }), 400
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Ensure we read committed data
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
        
        # Convert datetime to string for JSON serialization
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
        
        # CRITICAL: Commit the deletion
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
    """Get statistics about reviews"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
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
    """Health check endpoint for monitoring"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Also check reviews table and count
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
    """Detailed connection test for debugging"""
    results = {}
    conn = None
    cursor = None
    
    try:
        # Test 1: Connection pool
        results['connection_pool'] = 'OK'
        
        # Test 2: Get connection
        conn = get_connection()
        results['get_connection'] = 'OK'
        
        # Test 3: Execute query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        results['execute_query'] = 'OK'
        
        # Test 4: Check table exists
        cursor.execute("SHOW TABLES LIKE 'reviews'")
        if cursor.fetchone():
            results['table_exists'] = 'OK'
        else:
            results['table_exists'] = 'FAILED - Table not found'
        
        # Test 5: Count reviews
        cursor.execute("SELECT COUNT(*) FROM reviews")
        count = cursor.fetchone()[0]
        results['review_count'] = count
        
        # Test 6: Get recent reviews
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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host="0.0.0.0", debug=False, port=port)
    
