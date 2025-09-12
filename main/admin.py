"""Django admin functionality that is relevant to the entire app"""

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME


class AuditableModelAdmin(admin.ModelAdmin):
    """A ModelAdmin which will save and log"""

    def save_model(self, request, obj, form, change):  # noqa: ARG002
        obj.save_and_log(request.user)


class SingletonModelAdmin(admin.ModelAdmin):
    """A ModelAdmin which enforces a singleton model"""

    def has_add_permission(self, request):  # noqa: ARG002
        """Overridden method - prevent adding an object if one already exists"""
        return self.model.objects.count() == 0


class ModelAdminRunActionsForAllMixin:
    """
    Mixin to allow admin actions to run even when no items are selected.

    By default, Django admin actions only run on selected items. This mixin
    allows you to specify certain actions that should run on all items if none
    are selected. This is useful for actions that are intended to affect all records,
    such as maintenance or cleanup tasks.
    """

    run_for_all_actions: list[str] = []  # override in your admin

    def get_action_object_ids(self, request, action):  # noqa: ARG002
        """
        Get object IDs for the actions.

        As a hack, it will return just one ID to trigger the action, which
        can then handle all objects as needed. The reason for this is that
        Django admin actions require at least one selected item to run. If
        your action needs to process all items, you can override this method.
        Args:
            request(HttpRequest): The current request object.
            action(str): The action being performed.

        Returns:
            QuerySet: A queryset of all object IDs for the model.
        """
        return self.model.objects.values_list("pk", flat=True)[:1]

    def changelist_view(self, request, extra_context=None):
        action = request.POST.get("action")
        selected = request.POST.getlist(ACTION_CHECKBOX_NAME)

        if action in getattr(self, "run_for_all_actions", []) and not selected:
            # Replace POST with all object IDs
            post = request.POST.copy()
            post.setlist(
                ACTION_CHECKBOX_NAME,
                self.get_action_object_ids(request, action),
            )
            request._set_post(post)  # noqa: SLF001

        return super().changelist_view(request, extra_context)
