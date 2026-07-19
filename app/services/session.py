import uuid


class SessionManager:

    def new_session(self):

        return str(uuid.uuid4())