import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from graphene_django.views import GraphQLView

from payables.adapters.identity.invalid_token_error import InvalidTokenError
from payables.adapters.identity.jwt_verifier import verifier_from_settings
from payables.adapters.orm.tenancy import tenant_transaction
from payables.entrypoints.graphql.authentication import authenticate
from payables.entrypoints.graphql.error_mapper import (
    UNAUTHENTICATED,
    format_error,
    transport_status,
    unauthenticated_body,
)

logger = logging.getLogger(__name__)


class TenantGraphQLView(GraphQLView):
    format_error = staticmethod(format_error)

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            principal = authenticate(request, verifier_from_settings())
        except InvalidTokenError as error:
            logger.info("token refused: %s", error)
            return _unauthenticated()

        request.principal = principal
        with tenant_transaction(principal.tenant_id):
            return super().dispatch(request, *args, **kwargs)

    def execute_graphql_request(self, request, *args, **kwargs):
        result = super().execute_graphql_request(request, *args, **kwargs)
        self._transport_status = transport_status(result.errors if result else None)
        return result

    def get_response(self, request, data, show_graphiql=False):
        body, status = super().get_response(request, data, show_graphiql)
        return body, getattr(self, "_transport_status", None) or status


def _unauthenticated() -> JsonResponse:
    response = JsonResponse(unauthenticated_body(), status=UNAUTHENTICATED.status)
    response["WWW-Authenticate"] = "Bearer"
    return response
