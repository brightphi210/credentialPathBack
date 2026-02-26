# urls.py - UPDATED with verification endpoints

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

urlpatterns = [
    # ==================== AUTHENTICATION ====================
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ==================== EMAIL VERIFICATION ====================
    path('verify-otp/', verify_email_otp, name='verify_email_otp'),
    path('resend-otp/', resend_verification_otp, name='resend_verification_otp'),
    
    # ==================== PROFILE ====================
    path('profile/', get_user_profile, name='get_profile'),
    path('profile/update/', update_user_profile, name='update_profile'),
    path('change-password/', change_password, name='change_password'),

    # ==================== CERTIFICATES (Protected) ====================
    path('certificate/', CertificateListView.as_view(), name='certificate_list'),
    path('certificate/create/', create_single_certificate, name='create_certificate'),
    path('certificate/bulk-create/', create_bulk_certificates, name='bulk_create_certificates'),
    path('certificate/monthly-data/', get_monthly_certificate_data, name='monthly-certificate-data'),
    path('certificate/recent-activity/', get_recent_activity, name='recent-activity'),
    path('certificate/<int:certificate_id>/', get_certificate_detail, name='certificate_detail'),
    path('certificate/<int:certificate_id>/update/', update_certificate, name='update_certificate'),
    path('certificate/<int:certificate_id>/revoke/', revoke_certificate, name='revoke_certificate'),
    path('certificate/<int:certificate_id>/delete/', delete_certificate, name='delete_certificate'),
    
    # ==================== STATS ====================
    path('stats/', get_certificate_stats, name='certificate_stats'),
    
    # ==================== PUBLIC VERIFICATION ENDPOINTS ====================
    path('certificate/verify/search/', search_certificate, name='search_certificate'),
    path('certificate/verify/<str:credential_id>/', verify_certificate, name='verify_certificate'),
    
    
    path('badges/', get_badges,                   name='get_badges'),
    path('badges/stats/',                          get_badge_stats,              name='badge_stats'),
    path('badges/<int:badge_id>/',                 get_badge_detail,             name='badge_detail'),
    path('badges/credential/<str:credential_id>/', get_badge_by_credential,      name='badge_by_credential'),
    path('badges/verify/<str:credential_id>/',     verify_badge,                 name='verify_badge'),
    # ==================== NOTIFICATIONS ====================
    path('notifications/', get_notifications, name='get_notifications'),
    path('notifications/clear-all/', clear_all_notifications, name='clear_all_notifications'),
    path('notifications/<int:notification_id>/delete/', delete_notification, name='delete_notification'),
]