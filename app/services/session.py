import uuid


class SessionManager:
    def new_session(self) -> str:
        return str(uuid.uuid4())
