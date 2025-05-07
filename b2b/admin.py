"""B2B model admin. Only for convenience; you should use the Wagtail interface instead."""

from django.contrib import admin

from b2b.models import ContractPage, OrganizationPage

admin.site.register(OrganizationPage)
admin.site.register(ContractPage)
