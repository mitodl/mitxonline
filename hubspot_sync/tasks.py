"""
Hubspot tasks
"""

import logging
from math import ceil
from typing import List, Tuple  # noqa: UP035

import celery
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from hubspot.crm.associations import BatchInputPublicAssociation, PublicAssociation
from hubspot.crm.objects import (
    ApiException,
)
from hubspot.crm.objects import (
    BatchInputSimplePublicObjectBatchInputForCreate as BatchInputCreate,
)
from mitol.common.decorators import single_task
from mitol.common.utils.collections import chunks
from mitol.common.utils.datetime import now_in_utc
from mitol.hubspot_api.api import HubspotApi, HubspotAssociationType, HubspotObjectType
from mitol.hubspot_api.decorators import raise_429
from mitol.hubspot_api.exceptions import TooManyRequestsException
from mitol.hubspot_api.models import HubspotObject

from ecommerce.models import Line, Order, Product
from hubspot_sync import api
from hubspot_sync.api import (
    get_hubspot_id_for_object,
)
from hubspot_sync.rate_limiter import wait_for_hubspot_rate_limit
from main.celery import app
from users.models import User

log = logging.getLogger(__name__)


def task_obj_lock(
    func_name: str,
    args: List[object],  # noqa: UP006
    kwargs: dict,  # noqa: ARG001
) -> str:  # @pylint:unused-argument
    """
    Determine a task lock name for a specific task function and object id

    Args:
        func_name(str): Name of a task function
        args: Task function arguments, first should be object id
        kwargs: Any keyword arguments sent to the task function

    Returns:
        str: The lock id for the task and object
    """
    return f"{func_name}_{args[0]}"


def max_concurrent_chunk_size(obj_count: int) -> int:
    """
    Divide number of objects by max concurrent tasks for chunk size

    Args:
        obj_count: Number of objects

    Returns:
        int: chunk size to use
    """
    return ceil(obj_count / settings.HUBSPOT_MAX_CONCURRENT_TASKS)


def _batched_chunks(
    hubspot_type: str,
    batch_ids: List[int or (int, str)],  # noqa: UP006
) -> List[List[int or str]]:  # noqa: UP006
    """
    If list of ids exceed max allowed in a batch API call, chunk them up

    Args:
        hubspot_type(str): The type of hubspot object (deal, contact, etc)
        batch_ids(list): The list of object ids to process

    Returns:
        list(list): List of chunked ids
    """
    max_chunk_size = 10 if hubspot_type == api.HubspotObjectType.CONTACTS.value else 100
    if len(batch_ids) <= max_chunk_size:
        return [batch_ids]
    return chunks(batch_ids, chunk_size=max_chunk_size)


def sync_failed_contacts(chunk: List[int]) -> List[int]:  # noqa: UP006
    """
    Consecutively try individual contact syncs for a failed batch sync
    Args:
        chunk[list]: list of user id's

    Returns:
        list of contact ids that still failed
    """
    failed_ids = []
    users = list(User.objects.filter(id__in=chunk))
    for user in users:
        try:
            # Use intelligent rate limiting instead of fixed delay
            wait_for_hubspot_rate_limit()
            api.sync_contact_with_hubspot(user)
        except ApiException:  # noqa: PERF203
            failed_ids.append(user.id)
    return failed_ids


def handle_failed_batch_chunk(chunk: List[int], hubspot_type: str) -> List[int]:  # noqa: UP006
    """
    Try reprocessing a chunk of contacts individually, in case conflicting emails are the problem

    Args:
        chunk [list]: list of object ids
        hubspot_type: The type of Hubspot object

    Returns:
        list of still failing object ids

    """
    failed = chunk
    if hubspot_type == HubspotObjectType.CONTACTS.value:
        # Might be due to conflicting emails, try updating individually
        failed = sync_failed_contacts(chunk)
    if failed:
        log.exception(
            "Exception when batch syncing Hubspot ids %s of type %s",
            f"{failed}",
            hubspot_type,
        )
    return failed


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException, BlockingIOError),
    max_retries=5,  # Increased retries for rate limits
    retry_backoff=120,  # Longer initial backoff
    retry_jitter=True,
    retry_backoff_max=600,  # Cap backoff at 10 minutes
)
@raise_429
@single_task(10, key=task_obj_lock)
def sync_contact_with_hubspot(user_id: int) -> str:
    """
    Sync a User with a hubspot contact

    Args:
        user_id(int): The User ID.

    Returns:
        str: The HubSpot ID for the User.
    """
    return api.sync_contact_with_hubspot(User.objects.get(id=user_id)).id


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException, BlockingIOError),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
@single_task(10, key=task_obj_lock)
def sync_product_with_hubspot(product_id: int) -> str:
    """
    Sync a MITxOnline Product with a hubspot product

    Args:
        product_id(int): The Product ID.

    Returns:
        str: The hubspot id for the product
    """
    return api.sync_product_with_hubspot(Product.objects.get(id=product_id)).id


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException, BlockingIOError),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
@single_task(10, key=task_obj_lock)
def sync_deal_with_hubspot(order_id: int) -> str:
    """
    Sync an Order with a hubspot deal

    Args:
        order_id(int): The Order ID.

    Returns:
        str: The hubspot id for the deal
    """
    return api.sync_deal_with_hubspot(Order.objects.get(id=order_id)).id


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException, BlockingIOError),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
@single_task(10, key=task_obj_lock)
def sync_line_with_hubspot(line_id: int) -> str:
    """
    Sync a Line with a hubspot line

    Args:
        line_id(int): The Line id

    Returns:
        str: The hubspot id for the line
    """
    return api.sync_line_item_with_hubspot(Line.objects.get(id=line_id)).id


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException,),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
def batch_create_hubspot_objects_chunked(
    hubspot_type: str,
    ct_model_name: str,
    object_ids: List[int],  # noqa: UP006
) -> List[str]:  # noqa: UP006
    """
    Batch create or update a list of hubspot objects, no associations

    Args:
        hubspot_type(str): The hubspot object type (deal, contact, etc)
        ct_model_name(str): The corresponding model name
        object_ids: List of object ids to process

    Returns:
          list(str): list of processed hubspot ids
    """
    created_ids = []
    content_type = ContentType.objects.exclude(app_label="auth").get(
        model=ct_model_name
    )
    chunked_ids = _batched_chunks(hubspot_type, object_ids)
    errored_chunks = []
    last_error_status = None
    for chunk in chunked_ids:
        try:
            response = HubspotApi().crm.objects.batch_api.create(
                hubspot_type,
                BatchInputCreate(
                    inputs=api.MODEL_CREATE_FUNCTION_MAPPING[ct_model_name](chunk)
                ),
            )
            for result in response.results:
                if ct_model_name == "user":
                    user = User.objects.filter(
                        email__iexact=result.properties["email"], is_active=True
                    ).first()
                    user.hubspot_sync_datetime = now_in_utc()
                    user.save()
                    object_id = user.id
                else:
                    object_id = result.properties["unique_app_id"].split("-")[-1]
                HubspotObject.objects.update_or_create(
                    content_type=content_type,
                    hubspot_id=result.id,
                    object_id=object_id,
                )
                created_ids.append(result.id)
        except ApiException as ae:
            last_error_status = ae.status
            still_failed = handle_failed_batch_chunk(chunk, hubspot_type)
            if still_failed:
                errored_chunks.append(still_failed)
        wait_for_hubspot_rate_limit()
    if errored_chunks:
        raise ApiException(
            status=last_error_status,
            reason=f"Batch hubspot create failed for the following chunks: {errored_chunks}",
        )
    return created_ids


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException,),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
def batch_update_hubspot_objects_chunked(
    hubspot_type: str,
    ct_model_name: str,
    object_ids: List[Tuple[int, str]],  # noqa: UP006
) -> List[str]:  # noqa: UP006
    """
    Batch create or update hubspot objects, no associations

    Args:
        hubspot_type(str): The hubspot object type (deal, contact, etc)
        ct_model_name(str): The corresponding model name
        object_ids: List of (object id, hubspot id) tuples to process

    Returns:
          list(str): list of processed hubspot ids
    """
    updated_ids = []
    chunked_ids = _batched_chunks(hubspot_type, object_ids)
    errored_chunks = []
    last_error_status = None
    for chunk in chunked_ids:
        inputs = api.MODEL_UPDATE_FUNCTION_MAPPING[ct_model_name](chunk)
        try:
            response = HubspotApi().crm.objects.batch_api.update(
                hubspot_type, BatchInputCreate(inputs=inputs)
            )
            chunk_updated_ids = [result.id for result in response.results]
            for result in response.results:
                if ct_model_name == "user":
                    User.objects.filter(
                        email__iexact=result.properties["email"], is_active=True
                    ).update(hubspot_sync_datetime=now_in_utc())
            updated_ids.extend(chunk_updated_ids)
            log.info("Updated the following HubSpot ID's %s", chunk_updated_ids)
            percent_complete = (len(updated_ids) / len(object_ids)) * 100
            log.info("%i%% complete updating HubSpot ID's", percent_complete)
        except ApiException as ae:
            last_error_status = ae.status
            still_failed = handle_failed_batch_chunk(
                [item[0] for item in chunk], hubspot_type
            )
            if still_failed:
                errored_chunks.append(still_failed)
        wait_for_hubspot_rate_limit()
    if errored_chunks:
        raise ApiException(
            status=last_error_status,
            reason=f"Batch hubspot update failed for the following chunks: {errored_chunks}",
        )
    return updated_ids


@app.task(bind=True)
@single_task(10, key=task_obj_lock)
def sync_all_contacts_with_hubspot(self):
    hubspot_type = HubspotObjectType.CONTACTS.value
    model_name = ContentType.objects.get_for_model(User).model
    app_label = User._meta.app_label  # noqa: SLF001
    raise self.replace(
        batch_upsert_hubspot_objects(hubspot_type, model_name, app_label, False)  # noqa: FBT003
    )


@app.task(bind=True)
def batch_upsert_hubspot_objects(  # pylint:disable=too-many-arguments  # noqa: PLR0913
    self,
    hubspot_type: str,
    model_name: str,
    app_label: str,
    create: bool = True,  # noqa: FBT001, FBT002
    object_ids: List[int] = None,  # noqa: UP006, RUF013
):
    """
    Batch create or update objects in hubspot, no associations (so ideal for contacts and products)

    Args:
        hubspot_type(str): The hubspot object type (deal, contact, etc)
        model_name(str): The corresponding model name
        app_label(str): The model's containing app
        create(bool): Create if true, update if false
        object_ids(list): List of specific object ids to process if any
    """
    content_type = ContentType.objects.get_by_natural_key(app_label, model_name)
    if not object_ids:
        synced_object_ids = HubspotObject.objects.filter(
            content_type=content_type
        ).values_list("object_id", "hubspot_id")
        unsynced_objects = content_type.model_class().objects.exclude(
            id__in=[id[0] for id in synced_object_ids]  # noqa: A001
        )
        if model_name == "user":
            unsynced_objects = (
                unsynced_objects.filter(is_active=True, email__contains="@")
                .exclude(social_auth__isnull=True)
                .order_by(F("hubspot_sync_datetime").asc(nulls_first=True))
            )
        unsynced_object_ids = unsynced_objects.values_list("id", flat=True)
        object_ids = unsynced_object_ids if create else synced_object_ids
    elif not create:
        object_ids = HubspotObject.objects.filter(
            content_type=content_type, object_id__in=object_ids
        ).values_list("object_id", "hubspot_id")
    # Limit number of chunks to avoid rate limit
    chunk_size = max_concurrent_chunk_size(len(object_ids))
    chunk_func = (
        batch_create_hubspot_objects_chunked
        if create
        else batch_update_hubspot_objects_chunked
    )
    chunked_tasks = [
        chunk_func.s(hubspot_type, model_name, chunk)
        for chunk in chunks(sorted(object_ids), chunk_size=chunk_size)
    ]
    raise self.replace(celery.group(chunked_tasks))


@app.task(
    acks_late=True,
    autoretry_for=(TooManyRequestsException,),
    max_retries=3,
    retry_backoff=60,
    retry_jitter=True,
)
@raise_429
def batch_upsert_associations_chunked(order_ids: List[int]):  # noqa: UP006
    """
    Upsert batches of deal-contact and line-deal associations

    Args:
        order_ids(list): List of Order IDs
    """
    contact_associations_batch = []
    line_associations_batch = []
    hubspot_client = HubspotApi()
    deal_count = len(order_ids)
    for idx, order_id in enumerate(order_ids):
        deal = Order.objects.get(id=order_id)
        contact_id = get_hubspot_id_for_object(deal.purchaser)
        deal_id = get_hubspot_id_for_object(deal)
        for line in deal.lines.iterator():
            line_id = get_hubspot_id_for_object(line)
            if contact_id and deal_id:
                contact_associations_batch.append(
                    PublicAssociation(
                        _from=deal_id,
                        to=contact_id,
                        type=HubspotAssociationType.DEAL_CONTACT.value,
                    )
                )
            if line_id and deal_id:
                line_associations_batch.append(
                    PublicAssociation(
                        _from=line_id,
                        to=deal_id,
                        type=HubspotAssociationType.LINE_DEAL.value,
                    )
                )
            if (
                len(contact_associations_batch) == 100  # noqa: PLR2004
                or len(line_associations_batch) == 100  # noqa: PLR2004
                or idx == deal_count - 1
            ):
                hubspot_client.crm.associations.batch_api.create(
                    HubspotObjectType.LINES.value,
                    HubspotObjectType.DEALS.value,
                    batch_input_public_association=BatchInputPublicAssociation(
                        inputs=line_associations_batch
                    ),
                )
                line_associations_batch = []
                hubspot_client.crm.associations.batch_api.create(
                    HubspotObjectType.DEALS.value,
                    HubspotObjectType.CONTACTS.value,
                    batch_input_public_association=BatchInputPublicAssociation(
                        inputs=contact_associations_batch
                    ),
                )
                contact_associations_batch = []
    return order_ids


@app.task(bind=True)
def batch_upsert_associations(self, order_ids: List[int] = None):  # noqa: UP006, RUF013
    """
    Upsert chunked batches of deal-contact and line-deal associations

    Args:
        order_ids(list): List of Order IDs
    """
    deal_ids = Order.objects.all()
    if order_ids:
        deal_ids = deal_ids.filter(id__in=order_ids)
    deal_ids = deal_ids.values_list("id", flat=True)
    chunk_size = max_concurrent_chunk_size(len(deal_ids))
    chunked_tasks = [
        batch_upsert_associations_chunked.s(chunk)
        for chunk in chunks(sorted(deal_ids), chunk_size=chunk_size)
    ]
    raise self.replace(celery.group(chunked_tasks))
