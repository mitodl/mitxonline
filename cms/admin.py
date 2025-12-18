"""
Admin configurations for CMS models
"""

from django.contrib import admin
from wagtail.models import Revision


@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    """
    Custom admin for Wagtail Revision model to enable search functionality
    for Certificate Page revisions used in CourseRunCertificate admin.
    """
    
    list_display = ['id', 'get_page_title', 'get_page_product_name', 'created_at', 'user']
    list_filter = ['content_type', 'created_at']
    search_fields = [
        'object_str',  # The string representation of the page
        'user__username',  # User who created the revision
        'user__email',  # User email
    ]
    readonly_fields = ['created_at', 'content_type', 'object_id', 'content_object']
    ordering = ['-created_at']
    
    def get_page_title(self, obj):
        """Get the title of the certificate page"""
        try:
            page = obj.as_object()
            if hasattr(page, 'title'):
                return page.title
            return str(page)
        except:
            return "Unknown"
    get_page_title.short_description = 'Page Title'
    
    def get_page_product_name(self, obj):
        """Get the product name of the certificate page"""
        try:
            page = obj.as_object()
            if hasattr(page, 'product_name'):
                return page.product_name
            return "N/A"
        except:
            return "N/A"
    get_page_product_name.short_description = 'Product Name'
    
    def __str__(self):
        """Custom string representation for better display in autocomplete"""
        return f"Revision {self.id}"
    
    def get_search_results(self, request, queryset, search_term):
        """
        Custom search to improve search functionality by searching in 
        the actual page content when possible.
        """
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        
        if search_term:
            queryset |= self.model.objects.filter(
                content_type__app_label='cms',
                content_type__model='certificatepage'
            ).filter(
                object_str__icontains=search_term
            )
            use_distinct = True
            
        return queryset, use_distinct
    
    def get_queryset(self, request):
        """
        Filter to show only revisions of CertificatePage for better performance
        and relevance when selecting certificate page revisions.
        """
        qs = super().get_queryset(request)
        # Only show revisions for CertificatePage objects
        return qs.filter(
            content_type__app_label='cms',
            content_type__model='certificatepage'
        ).select_related('user', 'content_type').prefetch_related('content_object')
    
    def has_add_permission(self, request):
        """
        Disable adding revisions through admin - they should be created
        through the Wagtail interface.
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """
        Disable editing revisions through admin - they are immutable.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Disable deleting revisions through admin for data integrity.
        """
        return False