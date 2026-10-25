from app.core.settings import settings
from app.providers.registry import ProviderRegistry
from app.registry.service import RegistryService
from app.router.engine import RouterEngine
from app.services.cache import Cache
from app.services.history import HistoryManager
from app.services.mendix import MendixService
from app.services.operations import Operations
from app.services.review import RepositoryReview
from app.services.session import SessionManager
from app.services.workspace import Workspace


class Container:
    def __init__(self) -> None:
        self.provider_registry = ProviderRegistry()

        self.history = HistoryManager()

        self.cache = Cache()

        self.session = SessionManager()

        self.registry = RegistryService(self.provider_registry)

        self.router = RouterEngine(
            provider_registry=self.provider_registry,
            registry=self.registry,
            history=self.history,
        )

        self.workspace = Workspace(settings.workspace_root, settings.state_dir)
        self.operations = Operations(self.workspace, settings)
        self.review = RepositoryReview(self.workspace, self.router)
        self.mendix = MendixService(settings, self.workspace, self.router)


container: Container = Container()
