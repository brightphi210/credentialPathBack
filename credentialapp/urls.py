from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Profile
    path('profile/', get_user_profile, name='get_profile'),
    path('profile/update/', update_user_profile, name='update_profile'),
    path('change-password/', change_password, name='change_password'),

    # Email Verification with OTP
    path('verify-otp/', verify_email_otp, name='verify_email_otp'),
    path('resend-otp/', resend_verification_otp, name='resend_verification_otp'),

    # Certificates
    path('certificate/', CertificateListView.as_view(), name='certificate_list'),
    path('certificate/create/', create_single_certificate, name='create_certificate'),
    path('certificate/bulk-create/', create_bulk_certificates, name='bulk_create_certificates'),
    path('certificate/<int:certificate_id>/', get_certificate_detail, name='certificate_detail'),
    path('certificate/<int:certificate_id>/update/', update_certificate, name='update_certificate'),
    path('certificate/<int:certificate_id>/revoke/', revoke_certificate, name='revoke_certificate'),
    path('certificate/<int:certificate_id>/delete/', delete_certificate, name='delete_certificate'),

    path('certificate/monthly-data/', get_monthly_certificate_data, name='monthly-certificate-data'),
    path('certificate/recent-activity/', get_recent_activity, name='recent-activity'),
    
    # Stats and Verification
    path('stats/', get_certificate_stats, name='certificate_stats'),
    path('verify/<str:credential_id>/', verify_certificate, name='verify_certificate'),
]