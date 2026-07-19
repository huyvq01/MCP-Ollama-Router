class AIRouterException(Exception):
    pass


class ProviderNotFound(AIRouterException):
    pass


class ModelNotFound(AIRouterException):
    pass


class ProviderUnavailable(AIRouterException):
    pass