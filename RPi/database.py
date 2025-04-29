import mysql.connector

def setup():
    db = mysql.connector.connect(
        host="192.168.67.226",
        user="server",
        password="server",
    )
    cursor = db.cursor()
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS smart_lock")
        print("Database created")
        cursor.execute("USE smart_lock")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person (
                id INT AUTO_INCREMENT PRIMARY KEY,
                person_name VARCHAR(255) UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_embedding (
                id INT AUTO_INCREMENT PRIMARY KEY,
                person_id INT NOT NULL,
                file_path VARCHAR(255) NOT NULL,
                embedding_vector BLOB NOT NULL,
                FOREIGN KEY (person_id) REFERENCES person(id)                       
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                video_file TEXT,
                access_method VARCHAR(255) NOT NULL,
                access_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                person_id INT,
                FOREIGN KEY (person_id) REFERENCES person(id)
            )
        """)
        db.commit()
    except Exception as e:
        print(f"MySQL Error: {e}")
    
    return db, cursor
