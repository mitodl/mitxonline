"""Constants for the compliance app"""

# Maps CyberSource bill-to field names to the profile field names an API
# consumer should show the user as missing.
BILL_TO_FIELD_TO_PROFILE_FIELD = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "address1": "street_address_1",
    "locality": "city",
    "country": "country",
    "administrative_area": "state",
    "postal_code": "postal_code",
}
