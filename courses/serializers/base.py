from urllib.parse import urljoin

from django.conf import settings
from django.templatetags.static import static
from rest_framework import serializers

from courses import models


def get_thumbnail_url(page):
    """
    Get the thumbnail URL or else return a default image URL.

    Args:
        page (cms.models.ProductPage): A product page

    Returns:
        str:
            A page URL
    """
    relative_url = (
        page.thumbnail_image.file.url
        if page
        and page.thumbnail_image
        and page.thumbnail_image.file
        and page.thumbnail_image.file.url
        else static("images/mit-dome.png")
    )
    return urljoin(settings.SITE_BASE_URL, relative_url)


class BaseProgramRequirementTreeSerializer(serializers.ListSerializer):
    """
    Serializer for root nodes of a program requirement tree

    The instance is considered immutable and the data passed in
    is expected to be a list of objects in the structure that ProgramRequirement.load_bulk()
    can consume.
    """

    def update(self, instance, validated_data):  # noqa: C901
        """
        Update the program requirement tree

        This is inspired by the load_bulk method, but that method is an append-only operation and doesn't update existing records
        """
        keep_node_ids = []

        def _get_existing(data):
            node_id = data.get("id", None)
            return (
                models.ProgramRequirement.objects.filter(id=node_id).first()
                if node_id
                else None
            )

        # we'll recursively walk the tree, in practice this is at most 3 deep under instance (OPERATOR -> OPERATOR -> COURSE)
        def _update(parent, children_data):
            last_updated_child = None

            for node_data in children_data:
                parent.refresh_from_db()
                first_child = parent.get_first_child()
                existing_child = _get_existing(node_data)

                data = {
                    **node_data["data"],
                    "program_id": instance.program_id,
                }
                children = node_data.get("children", [])

                if existing_child is None:
                    # we're inserting a new node
                    if last_updated_child is not None:
                        # insert after the last node we updated or inserted
                        last_updated_child = last_updated_child.add_sibling(
                            "right", **data
                        )
                    elif first_child is not None:
                        # otherwise insert as the first sibling
                        last_updated_child = first_child.add_sibling(
                            "first-sibling", **data
                        )
                    else:
                        # insert as a regular child node as there's no children yet
                        last_updated_child = parent.add_child(**data)
                else:
                    # we have an existing node and need to move it and update it
                    if last_updated_child is not None:
                        # place it after the last node we updated
                        existing_child.move(last_updated_child, pos="right")
                    elif first_child is not None:
                        # move it to the first sibling
                        existing_child.move(first_child, "first-sibling")
                    elif parent is not None:
                        # this would only happen if the child is moving form another part of the tree, which
                        # we don't support at the moment but it's here for completeness and future-proofing
                        existing_child.move(parent, "first-child")

                    # since this is an existing node we need to update the props and save
                    for key, value in data.items():
                        setattr(existing_child, key, value)

                    existing_child.save(update_fields=data.keys())

                    last_updated_child = existing_child

                keep_node_ids.append(last_updated_child.id)

                # if the input has children, process those
                if children:
                    _update(last_updated_child, children)

        _update(instance, validated_data)

        # delete all descendants that didn't show up in the input
        instance.get_descendants().exclude(id__in=keep_node_ids).delete()

        instance.refresh_from_db()

        return instance

    @property
    def data(self):
        """Serializes the root node to a bulk dump of the tree"""
        # here we're bypassing Serializer.data implementation because it coerces
        # the to_representation return value into a dict of its keys
        return models.ProgramRequirement.dump_bulk(parent=self.instance, keep_ids=True)
