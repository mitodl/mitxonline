"""Authentication utils"""

import hashlib

from users.models import BlockList


def get_md5_hash(value):
    """Returns the md5 hash object for the given value"""
    return hashlib.md5(value.lower().encode("utf-8"))  # noqa: S324


def block_user_email(email):
    """Blocks the user's email if provided"""
    msg = None
    if email:
        hash_object = get_md5_hash(email)
        _, created = BlockList.objects.get_or_create(
            hashed_email=hash_object.hexdigest()
        )
        if created:
            msg = f"Email {email} is added to the blocklist of MITx Online."
        else:
            msg = f"Email {email} is already marked blocked for MITx Online."
    return msg
