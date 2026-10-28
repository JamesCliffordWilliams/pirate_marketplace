# Pirate Market Campus Marketplace
# CSC 404 Fall '26
# Created by Miles Walker - Iteration 3 - 10/25/26

from db import get_connection # Pull the get_connection function to establish a connection to the database

def user_exists(user_id): #Returns true if a user with this ID is in the users table
    conn = get_connection()
    cur = conn.cursor() #cursor actually sends SQL queries to the database
    cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
    #SELECT 1 checks that a row exists 
    #%s is a placeholder. Psycopg2 fills it in safely, which blocks SQL injection

    found = cur.fetchone() is not None #returns a row if one matched

    cur.close()
    conn.close()
    return found

def insert_message(sender_id, receiver_id, body, listing_id = None): #Saves new message and returns as a dictionary
    conn = get_connection()
    cur = conn.cursor() 
    cur.execute("""
        INSERT INTO messages (sender_id, receiver_id, listing_id, body)
        VALUES (%s, %s, %s, %s)
        RETURNING id, sender_id, receiver_id, listing_id, body, is_read, created_at;""", 
        (sender_id, receiver_id, listing_id, body))
    #Tuple order must match that of placeholders 

    row = cur.fetchone()

    conn.commit()
    cur.close()
    conn.close()
    return _row_to_dict(row) #Helper

def get_conversation(user_id, user2_id): #Returns all messages between two users, oldest first
    conn = get_connection()
    cur = conn.cursor()
    # A conversation goes both ways:
    #   user1 -> user2 (first half of the WHERE) and user2 -> user1 (after the OR)
    #

    cur.execute("""
        SELECT id, sender_id, receiver_id, listing_id, body, is_read, created_at
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at ASC;""", # puts the oldest messages first 
        (user_id, user2_id, user2_id, user_id))

    rows = cur.fetchall() #returns a list of every match row
    cur.close()
    conn.close()

    return [_row_to_dict(r) for r in rows] 
    #Turns each raw (plain) tuple into a dictionary, so jsonify can send it as JSON later

def get_inbox(user_id): 
# Returns one entry per conversation, showing the latest message and newest convo first
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM (
            SELECT DISTINCT ON (other_id)
                CASE WHEN m.sender_id = %s THEN m.receiver_id ELSE m.sender_id END AS other_id,
                u.username, m.body, m.created_at, m.is_read, m.sender_id
            FROM messages m 
            JOIN users u 
                ON u.id = CASE WHEN m.sender_id = %s THEN m.receiver_id ELSE m.sender_id END
            WHERE m.sender_id =  %s OR m.receiver_id = %s
            ORDER BY other_id, m.created_at DESC
        ) latest
        ORDER BY created_at DESC;""",
        (user_id, user_id, user_id, user_id)) #user id appears four times, one for each placeholder

    # Outer SELECT orders conversations by recency
    # CASE expression figures out who the other user is (whether they are the sender or recipient)
    # JOIN looks up the other user's username to be displayed in inbox
    # WHERE filters messages to only those involving the user
    # DISTINCT ON (other_id) keeps just the first row per person 

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [{
        "other_user_id": r[0],
        "other_username": r[1],
        "last_message": r[2],
        "created_at": r[3],
        "is_read": r[4],
        "last_sender_id": r[5] # lets the UI show the sender of the most recent message
    } for r in rows]

def mark_conversation_read(user_id, other_id): #Marks all messages that user2 sent to user_id as read
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE messages SET is_read = TRUE
        WHERE receiver_id = %s AND sender_id = %s AND is_read = FALSE;""",
        (user_id, other_id)) #You can only mark messages sent to you as read

    conn.commit() #Update changes data, so it needs a commit just like INSERT
    cur.close()
    conn.close()

def unread_count(user_id): #How many unread messages this user has
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM messages
        WHERE receiver_id = %s AND is_read = FALSE;""",
        (user_id,))
    # COUNT(*) returns a single row with a single number
    # This is the query that the idx_messages_receiver index was built for
    count = cur.fetchone()[0] #fetchone returns a tuple, so we take the first element

    cur.close()
    conn.close()
    return count

def _row_to_dict(row):
    """
    Converts a raw database tuple into a dictionary.
    The first underscore is a Python convention meaning "internal helper, don't import this from other files".
    The order here must match the column order in the SELECT or RETURNING 
    clauses, otherwise values end up under the wrong keys.
    """

    return {
        "id": row[0],
        "sender_id": row[1],
        "receiver_id": row[2],
        "listing_id": row[3],
        "body": row[4],
        "is_read": row[5],
        "created_at": row[6]
    }