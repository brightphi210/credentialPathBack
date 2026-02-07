from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = [
        'profile_image', 'company_logo', 'company_bio', 'company_address',
        'company_phone', 'linkedin_handle', 'twitter_handle',
        'facebook_handle', 'instagram_handle', 'default_signatory_name',
        'default_signatory_title'
    ]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['email', 'full_name', 'business_name', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'full_name', 'business_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'business_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'business_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_phone', 'company_address', 'created_at']
    search_fields = ['user__email', 'user__full_name', 'company_address']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'certificate_no', 'recipient', 'course', 'certificate_type',
        'status', 'issue_date', 'issuer', 'created_at'
    ]
    list_filter = ['certificate_type', 'status', 'issue_date', 'created_at']
    search_fields = [
        'certificate_no', 'credential_id', 'recipient',
        'course', 'issuer__email'
    ]
    readonly_fields = [
        'verification_link', 'qr_code', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('issuer', 'certificate_no', 'credential_id', 'status')
        }),
        ('Recipient & Course', {
            'fields': ('recipient', 'course', 'program')
        }),
        ('Certificate Details', {
            'fields': (
                'certificate_type', 'phrase', 'issue_date',
                'delivery_mode', 'competence_result', 'competence_expiry_date'
            )
        }),
        ('Signatory Information', {
            'fields': ('signatory_name', 'signatory_title')
        }),
        ('Issuer Details', {
            'fields': ('issuer_name', 'issuer_location')
        }),
        ('Verification', {
            'fields': ('verification_link', 'qr_code')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(issuer=request.user)