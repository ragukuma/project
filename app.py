from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import mysql.connector
from mysql.connector import pooling
import os
import traceback

app = Flask(__name__)

# FULL CORS FIX — solves "Failed to fetch"
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


# ------------------------------
# DATABASE CONFIGURATION
# ------------------------------
db_config = {
    "host": os.getenv("DB_HOST", "srv2108.hstgr.io"),
    "user": os.getenv("DB_USER", "u772270336_arvels"),
    "password": os.getenv("DB_PASSWORD", "Arvels123"),
    "database": os.getenv("DB_NAME", "u772270336_arvels"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "autocommit": True
}

# TRY TO CREATE CONNECTION POOL
connection_pool = None
try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="review_pool",
        pool_size=5,
        pool_reset_session=True,
        **db_config
    )
    print("✅ Connection pool created successfully")
except Exception as e:
    print("\n❌ ERROR: Could not create MySQL connection pool")
    print(str(e))
    print("⚠ Backend will run, but DB will fail until you whitelist the Render IP.\n")


def get_connection():
    """Get a connection from the pool safely"""
    if connection_pool is None:
        raise Exception("MySQL connection pool not initialized")

    conn = connection_pool.get_connection()
    conn.autocommit = True
    return conn


# ------------------------------
# DATABASE INITIALIZATION
# ------------------------------
def init_database():
    """Create reviews table if missing, without crashing backend"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                gender VARCHAR(50) DEFAULT 'Not specified',
                rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
                review TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_created_at (created_at DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        print("✅ Database initialized")

        cursor.close()
        conn.close()

    except Exception as e:
        print("\n⚠ WARNING — Database init failed:")
        print(str(e))
        print("Backend continues running.\n")


# Run database init
init_database()


# ------------------------------
# ROOT ENDPOINT
# ------------------------------
@app.route('/')
def home():
    return jsonify({"status": "running"})


# ------------------------------
# ADD REVIEW
# ------------------------------
@app.route('/api/reviews', methods=['POST'])
def add_review():
    try:
        data = request.json

        required = ["name", "email", "phone", "rating", "review"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return jsonify({"status": "error", "message": f"Missing: {field}"}), 400

        rating = int(data["rating"])
        if rating < 1 or rating > 5:
            return jsonify({"status": "error", "message": "Rating must be 1-5"}), 400

        gender = data.get("gender", "Not specified")

        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO reviews (name, email, phone, gender, rating, review, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """

        cursor.execute(query, (
            data["name"], data["email"], data["phone"],
            gender, rating, data["review"]
        ))

        new_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "id": new_id}), 201

    except Exception as e:
        print("❌ Error in add_review:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ------------------------------
# GET REVIEWS
# ------------------------------
@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, email, phone, gender, rating, review, created_at
            FROM reviews
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()

        for r in rows:
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")

        cursor.close()
        conn.close()

        return jsonify(rows)

    except Exception as e:
        print("❌ Error in get_reviews:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ------------------------------
# DELETE REVIEW
# ------------------------------
@app.route('/api/reviews/<int:id>', methods=['DELETE'])
def delete_review(id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM reviews WHERE id=%s", (id,))
        affected = cursor.rowcount

        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "Not found"}), 404

        return jsonify({"status": "success"})

    except Exception as e:
        print("❌ Error deleting:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ------------------------------
# HEALTH CHECK
# ------------------------------
@app.route('/api/health')
def health():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reviews")
        count = cursor.fetchone()[0]

        return jsonify({"status": "healthy", "total_reviews": count})

    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# ------------------------------
# RUN SERVER
# ------------------------------
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
