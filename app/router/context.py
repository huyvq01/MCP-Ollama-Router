from app.services.history import HistoryManager
from app.services.cache import Cache
from app.services.session import SessionManager


class RouterContext:

    def __init__(self):

        self.history = HistoryManager()

        self.cache = Cache()

        self.session = SessionManager()


context = RouterContext()