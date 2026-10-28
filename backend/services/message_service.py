# Created 10/26/2026 by Miles Walker
# Purpose: Sits between the controller and the model to decide 
# whether something is allowed before the model touches the DB

from models.messages_model import ( 
    insert_message, get_conversation, get_inbox,
    mark_conversation_read, unread_count, user_exists,
) #Import the model functions that we need

class MessageService: 
    MAX_LEN = 2000

    def send(self, sender_id, receiver_id, body, listing_id=None):
        
        # (body or "") protects against body being None 
        # Calling .strip() on None would crash, so None becomes "" first
        # .strip() removes leading and trailing whitespace, so a message of just spaces counts as empty 
        body = (body or "").strip()

        # Validate in order and return as soon as one check fails
        if not body:
            return False, "Message cannot be empty", None
        if len(body) > self.MAX_LEN:
            return False, f"Message too long (max {self.MAX_LEN})", None

        #If a user tries to message themself, this gives them a message instead of a DB error 
        if sender_id == receiver_id:
            return False, "You can't message yourself", None
        
        #Make sure recipient is a real user
        if not user_exists(receiver_id):
            return False, "Receiver not found", None
        try: 
            return True, "Sent", insert_message(sender_id, receiver_id, body, listing_id)
        except Exception as e:
            print(f"MESSAGE SEND ERROR: {e}")  # real database error, shown in the server terminal only - [Your Name] 10/27/26
            return False, "Failed to send message", None

    def conversation(self, user_id, other_id):
        mark_conversation_read(user_id, other_id)
        return get_conversation(user_id, other_id)

    def inbox(self, user_id):
        return get_inbox(user_id)

    def unread(self, user_id):
        return unread_count(user_id)

    