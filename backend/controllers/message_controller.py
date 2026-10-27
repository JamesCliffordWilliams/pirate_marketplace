# Created 10/26/2026 by Miles Walker
# Purpose: Handles HTTP requests, checks who is making them, hands the work to the service, and turns the result into an HTTP response

# Blueprint: groups routes into their own file instead of putting everything in app.py
# request: the incoming HTTP request
# jsonify: turns Python dicts and lists into a JSON HTTP Response
# session: Cookie-based storage in Flask that remembers who is logged in
from flask import Blueprint, request, jsonify, session
from services.message_service import MessageService

message_bp = Blueprint("message_bp", __name__, url_prefix="/api")
service = MessageService() #One service instance shared by all routes in the file

#Session ONLY
def current_user_id():
    return session.get("user_id")
    # Returns the logged-in user's ID, or None if nobody is logged in
    # Identity comes from the server-side session only
    # If it was read from the reqeuest (a header or the JSON body), any user could claim to be someone else

@message_bp.post("/messages")
def send_message():

    # Asks who is asking? Returns 401 if no one is logged in 
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    data =request.get_json(silent=True) or {}
    receiver_id = data.get("receiver_id") # Check the shape of the input before using it
    if not isinstance(receiver_id, int):
        return jsonify ({"error": "receiver_id must be an integer"}), 400
    ok, msg, result = service.send(uid, receiver_id, data.get("body"), data.get("listing_id")) #Hand off to the service 
    return (jsonify(result), 201) if ok else (jsonify({"error": msg}), 400)

@message_bp.get("/messages")
def inbox():
    uid = current_user_id()
    if not uid:
        return jsonify ({"error": "Unauthorized"}), 401
    return jsonify (service.inbox(uid))

@message_bp.get("/message/<int:other_id>")
def conversation(other_id):
    uid = current_user_id()
    if not uid:
        return jsonify ({"error": "Unauthorized"}), 401 
    return jsonify(service.conversation(uid, other_id))


@message_bp.get("/messages/unread-count")
def unread():
    uid = current_user_id()
    if not uid:
        return jsonify ({"error": "Unauthorized"}), 401
    return jsonify ({"unread": service.unread(uid)})