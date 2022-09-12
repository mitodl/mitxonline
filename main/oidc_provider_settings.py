from django.utils.translation import ugettext as _
from oauth2_provider.oauth2_validators import OAuth2Validator

class CustomOAuth2Validator(OAuth2Validator):
    # Set `oidc_claim_scope = None` to ignore scopes that limit which claims to return,
    # otherwise the OIDC standard scopes are used.

    def get_additional_claims(self, request):
        return {
            "is_staff": request.user.is_staff
        }
