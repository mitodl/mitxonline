from django.utils.translation import ugettext as _
from oauth2_provider.oauth2_validators import OAuth2Validator


class CustomOAuth2Validator(OAuth2Validator):
    def get_additional_claims(self, request):
        return {"is_staff": request.user.is_staff}
