from rest_framework import status, generics, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import Badge, Certificate, Notification, User, UserProfile
from .serializers import BadgeSerializer, BadgeListSerializer  # etc.
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChangePasswordSerializer, UpdateProfileSerializer, UserProfileSerializer, 
    CertificateSerializer, CreateCertificateSerializer,
    BulkCertificateSerializer, UpdateCertificateSerializer,
    RevokeCertificateSerializer, NotificationSerializer
)
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from datetime import datetime, timedelta

from .utils import send_verification_email, send_welcome_email, is_otp_valid, create_notification


class RegisterView(generics.CreateAPIView):
    """
    Register a new user
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email with OTP
        email_sent = send_verification_email(user, request)
        
        return Response({
            'message': 'Registration successful! Please check your email for the verification code.',
            'email_sent': email_sent,
            'email': user.email
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_otp(request):
    """
    Verify user email with OTP code
    POST /api/auth/verify-otp/
    Body: { "email": "user@example.com", "otp": "123456" }
    """
    email = request.data.get('email')
    otp = request.data.get('otp')
    
    if not email or not otp:
        return Response({
            'error': 'Email and OTP code are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        
        if user.is_email_verified:
            return Response({
                'message': 'Email already verified. You can login now.',
                'already_verified': True
            }, status=status.HTTP_200_OK)
        
        # Check if OTP is valid
        if not is_otp_valid(user):
            return Response({
                'error': 'OTP has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify OTP
        if user.email_verification_otp != otp:
            return Response({
                'error': 'Invalid OTP code. Please check and try again.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the user
        user.is_email_verified = True
        user.is_active = True
        user.email_verification_otp = None  # Clear OTP after use
        user.otp_created_at = None
        user.save()
        
        # Send welcome email
        send_welcome_email(user)
        
        return Response({
            'message': 'Email verified successfully! You can now login.',
            'verified': True
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': 'No account found with this email address'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    User login
    POST /api/auth/login/
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    
    # Check if user exists
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Check if email is verified
    if not user.is_email_verified:
        return Response({
            'error': 'Please verify your email before logging in. Check your inbox for the OTP code.',
            'email_verified': False,
            'email': email
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Authenticate user
    user = authenticate(email=email, password=password)
    
    if user is None:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_active:
        return Response({
            'error': 'Account is disabled. Please contact support.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Generate tokens
    refresh = RefreshToken.for_user(user)
    
    # Pass request context to serializer for image URLs
    user_serializer = UserSerializer(user, context={'request': request})
    
    return Response({
        'message': 'Login successful',
        'user': user_serializer.data,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get current user profile
    GET /api/auth/profile/
    """
    user = request.user
    serializer = UserSerializer(user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update user profile
    PUT/PATCH /api/auth/profile/update/
    """
    user = request.user
    profile = user.profile
    
    # Update user basic info
    if 'full_name' in request.data:
        user.full_name = request.data['full_name']
    if 'business_name' in request.data:
        user.business_name = request.data['business_name']
    user.save()
    
    # Update profile
    serializer = UpdateProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    
    # Return updated user data with request context
    user_serializer = UserSerializer(user, context={'request': request})
    
    return Response({
        'message': 'Profile updated successfully',
        'user': user_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    POST /api/auth/change-password/
    """
    user = request.user
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Check old password
    if not user.check_password(serializer.validated_data['old_password']):
        return Response({
            'error': 'Old password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Set new password
    user.set_password(serializer.validated_data['new_password'])
    user.save()
    
    return Response({
        'message': 'Password changed successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user (blacklist refresh token)
    POST /api/auth/logout/
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_otp(request):
    """
    Resend verification OTP
    POST /api/auth/resend-otp/
    Body: { "email": "user@example.com" }
    """
    email = request.data.get('email')
    
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        
        if user.is_email_verified:
            return Response({
                'message': 'Email already verified. You can login now.'
            }, status=status.HTTP_200_OK)
        
        # Resend verification email with new OTP
        email_sent = send_verification_email(user, request)
        
        if email_sent:
            return Response({
                'message': 'A new verification code has been sent to your email.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to send email. Please try again later.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except User.DoesNotExist:
        return Response({
            'error': 'No account found with this email address'
        }, status=status.HTTP_404_NOT_FOUND)


# ==================== CERTIFICATE VIEWS ====================

class CertificateListView(generics.ListAPIView):
    """
    List all certificates for authenticated user
    GET /api/certificates/
    """
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['recipient', 'course', 'certificate_no', 'credential_id']
    ordering_fields = ['created_at', 'issue_date', 'recipient']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Certificate.objects.filter(issuer=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        # Filter by certificate type
        cert_type = self.request.query_params.get('type', None)
        if cert_type:
            queryset = queryset.filter(certificate_type=cert_type)
        
        # Filter by program
        program = self.request.query_params.get('program', None)
        if program:
            queryset = queryset.filter(program=program)
        
        return queryset


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_single_certificate(request):
    """
    Create a single certificate
    POST /api/certificates/create/
    """
    user = request.user
    serializer = CreateCertificateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    
    certificate = Certificate.objects.create(
        issuer=user,
        issuer_name=user.business_name or user.full_name,
        issuer_location=user.profile.company_address,
        **serializer.validated_data
    )
    
    return Response({
        'message': 'Certificate created successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bulk_certificates(request):
    """
    Create multiple certificates at once
    POST /api/certificates/bulk-create/
    """
    serializer = BulkCertificateSerializer(
        data=request.data,
        context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    certificates = serializer.save()
    
    return Response({
        'message': f'{len(certificates)} certificates created successfully',
        'certificates': CertificateSerializer(certificates, many=True).data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate_detail(request, certificate_id):
    """
    Get certificate details
    GET /api/certificates/<id>/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    serializer = CertificateSerializer(certificate)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_certificate(request, certificate_id):
    """
    Update certificate
    PUT/PATCH /api/certificates/<id>/update/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    serializer = UpdateCertificateSerializer(
        certificate,
        data=request.data,
        partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    
    return Response({
        'message': 'Certificate updated successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_certificate(request, certificate_id):
    """
    Revoke a certificate
    POST /api/certificates/<id>/revoke/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    if certificate.status == 'revoked':
        return Response({
            'error': 'Certificate is already revoked'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    certificate.status = 'revoked'
    certificate.save()
    
    return Response({
        'message': 'Certificate revoked successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_certificate(request, certificate_id):
    """
    Delete a certificate
    DELETE /api/certificates/<id>/delete/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    certificate.delete()
    
    return Response({
        'message': 'Certificate deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate_stats(request):
    """
    Get certificate statistics for dashboard
    GET /api/certificates/stats/
    """
    user = request.user
    certificates = Certificate.objects.filter(issuer=user)
    
    # Get current month
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    stats = {
        'total': certificates.count(),
        'active': certificates.filter(status='active').count(),
        'revoked': certificates.filter(status='revoked').count(),
        'this_month': certificates.filter(
            issue_date__month=current_month,
            issue_date__year=current_year
        ).count(),
        'by_type': {
            'completion': certificates.filter(certificate_type='Completion').count(),
            'competence': certificates.filter(certificate_type='Competence').count(),
            'attendance': certificates.filter(certificate_type='Attendance').count(),
        },
        'by_program': list(
            certificates.values('program')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
    }
    
    return Response(stats, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_monthly_certificate_data(request):
    """
    Get monthly certificate issuance data for charts
    GET /api/certificates/monthly-data/
    """
    user = request.user
    current_date = datetime.now()
    
    # Get last 6 months of data
    monthly_data = []
    for i in range(5, -1, -1):
        # Calculate the month
        target_date = current_date - timedelta(days=30 * i)
        month = target_date.month
        year = target_date.year
        
        # Count certificates issued in this month
        count = Certificate.objects.filter(
            issuer=user,
            issue_date__month=month,
            issue_date__year=year
        ).count()
        
        # Format month name
        month_name = target_date.strftime('%b')
        
        monthly_data.append({
            'month': month_name,
            'total': count
        })
    
    return Response(monthly_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_activity(request):
    """
    Get recent certificate activities
    GET /api/certificates/recent-activity/
    Query params:
        - limit: Number of activities to return (default: 5)
    """
    user = request.user
    limit = int(request.query_params.get('limit', 5))
    
    # Get recent certificates
    recent_certificates = Certificate.objects.filter(
        issuer=user
    ).order_by('-created_at')[:limit]
    
    # Format activity data
    activities = []
    for cert in recent_certificates:
        # Calculate time ago
        time_diff = datetime.now() - cert.created_at.replace(tzinfo=None)
        
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}d ago"
        elif time_diff.seconds // 3600 > 0:
            time_ago = f"{time_diff.seconds // 3600}h ago"
        else:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes}m ago" if minutes > 0 else "just now"
        
        activities.append({
            'id': cert.id,
            'recipient': cert.recipient,
            'type': cert.certificate_type,
            'course': cert.course,
            'date': time_ago,
            'status': cert.status,
            'created_at': cert.created_at.isoformat()
        })
    
    return Response(activities, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_certificate(request, credential_id):
    """
    Verify a certificate using credential ID
    GET /api/certificates/verify/<credential_id>/
    """
    try:
        certificate = Certificate.objects.get(credential_id=credential_id)
        
        if certificate.status == 'revoked':
            return Response({
                'valid': False,
                'message': 'This certificate has been revoked',
                'certificate': CertificateSerializer(certificate).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'valid': True,
            'message': 'Certificate is valid',
            'certificate': CertificateSerializer(certificate).data
        }, status=status.HTTP_200_OK)
        
    except Certificate.DoesNotExist:
        return Response({
            'valid': False,
            'message': 'Certificate not found'
        }, status=status.HTTP_404_NOT_FOUND)





# ==================== NOTIFICATION VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Get all notifications for authenticated user
    GET /api/notifications/
    Query params:
        - type: Filter by notification type (optional)
        - limit: Number of notifications to return (default: all)
    """
    user = request.user
    notifications = Notification.objects.filter(user=user)
    
    # Filter by type if provided
    notification_type = request.query_params.get('type', None)
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Limit if provided
    limit = request.query_params.get('limit', None)
    if limit:
        try:
            limit = int(limit)
            notifications = notifications[:limit]
        except ValueError:
            pass
    
    serializer = NotificationSerializer(notifications, many=True)
    return Response({
        'notifications': serializer.data,
        'total': notifications.count()
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """
    Delete a notification
    DELETE /api/notifications/<id>/delete/
    """
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    
    notification.delete()
    
    return Response({
        'message': 'Notification deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    """
    Clear all notifications for authenticated user
    DELETE /api/notifications/clear-all/
    """
    user = request.user
    deleted_count = Notification.objects.filter(user=user).delete()[0]
    
    return Response({
        'message': f'{deleted_count} notifications cleared successfully'
    }, status=status.HTTP_200_OK)


# ==================== UPDATED CERTIFICATE VIEWS WITH NOTIFICATIONS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_single_certificate(request):
    """
    Create a single certificate with notification
    POST /api/certificates/create/
    """
    user = request.user
    serializer = CreateCertificateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    
    certificate = Certificate.objects.create(
        issuer=user,
        issuer_name=user.business_name or user.full_name,
        issuer_location=user.profile.company_address,
        **serializer.validated_data
    )
    
    # Create notification
    create_notification(
        user=user,
        notification_type='certificate_created',
        title='Certificate Issued',
        message=f'Certificate for {certificate.recipient} has been successfully issued.',
        certificate=certificate
    )
    
    return Response({
        'message': 'Certificate created successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bulk_certificates(request):
    """
    Create multiple certificates at once with notification
    POST /api/certificates/bulk-create/
    """
    serializer = BulkCertificateSerializer(
        data=request.data,
        context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    certificates = serializer.save()
    
    # Create notification for bulk upload
    create_notification(
        user=request.user,
        notification_type='bulk_upload',
        title='Bulk Upload Complete',
        message=f'{len(certificates)} certificates have been successfully created from your upload.',
        certificate=None
    )
    
    return Response({
        'message': f'{len(certificates)} certificates created successfully',
        'certificates': CertificateSerializer(certificates, many=True).data
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_certificate(request, certificate_id):
    """
    Update certificate with notification
    PUT/PATCH /api/certificates/<id>/update/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    serializer = UpdateCertificateSerializer(
        certificate,
        data=request.data,
        partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    
    # Create notification
    create_notification(
        user=request.user,
        notification_type='certificate_updated',
        title='Certificate Updated',
        message=f'Certificate {certificate.certificate_no} for {certificate.recipient} has been updated.',
        certificate=certificate
    )
    
    return Response({
        'message': 'Certificate updated successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_certificate(request, certificate_id):
    """
    Revoke a certificate with notification
    POST /api/certificates/<id>/revoke/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    if certificate.status == 'revoked':
        return Response({
            'error': 'Certificate is already revoked'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    certificate.status = 'revoked'
    certificate.save()
    
    # Create notification
    create_notification(
        user=request.user,
        notification_type='certificate_revoked',
        title='Certificate Revoked',
        message=f'Certificate {certificate.certificate_no} has been revoked as requested.',
        certificate=certificate
    )
    
    return Response({
        'message': 'Certificate revoked successfully',
        'certificate': CertificateSerializer(certificate).data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_certificate(request, certificate_id):
    """
    Delete a certificate with notification
    DELETE /api/certificates/<id>/delete/
    """
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        issuer=request.user
    )
    
    cert_no = certificate.certificate_no
    recipient = certificate.recipient
    
    certificate.delete()
    
    # Create notification
    create_notification(
        user=request.user,
        notification_type='certificate_deleted',
        title='Certificate Deleted',
        message=f'Certificate {cert_no} for {recipient} has been permanently deleted.',
        certificate=None
    )
    
    return Response({
        'message': 'Certificate deleted successfully'
    }, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([AllowAny])
def search_certificate(request):
    """
    Public endpoint to search for a certificate by credential_id OR certificate_no

    POST /api/verify/search/
    Body: {
        "query": "CERT-2024-001" or "CRED-2024-001"
    }
    """
    query = request.data.get('query', '').strip()

    if not query:
        return Response({
            'status': 'error',
            'message': 'Query parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        certificate = None

        # Try credential_id first, then certificate_no
        try:
            certificate = Certificate.objects.get(credential_id=query)
        except Certificate.DoesNotExist:
            try:
                certificate = Certificate.objects.get(certificate_no=query)
            except Certificate.DoesNotExist:
                pass

        if certificate:
            serializer = CertificateSerializer(certificate)
            return Response({
                'status': 'verified',
                'message': 'Certificate found and verified successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': 'Certificate not found',
                'detail': 'No certificate matches your query. Please check the credential ID or certificate number.'
            }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': 'An error occurred during verification',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_certificate(request, credential_id):
    """
    Public endpoint to verify a certificate by credential_id

    GET /api/verify/<credential_id>/
    """
    try:
        certificate = Certificate.objects.get(credential_id=credential_id)
        serializer = CertificateSerializer(certificate)
        return Response({
            'status': 'verified',
            'message': 'Certificate verified successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    except Certificate.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Certificate not found',
            'detail': f'No certificate found with credential ID: {credential_id}'
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': 'An error occurred during verification',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badges(request):
    """
    List all badges for the authenticated user (issuer).
    Badges are auto-created when a Competence certificate is issued.

    GET /api/badges/
    Query params:
        - status: 'active' | 'revoked' | 'all' (default: all)
        - search: search by recipient, program, credential_id
    """
    user = request.user
    badges = Badge.objects.filter(issuer=user)

    # Filter by status
    status_filter = request.query_params.get('status', None)
    if status_filter and status_filter != 'all':
        badges = badges.filter(status=status_filter)

    # Search filter
    search = request.query_params.get('search', None)
    if search:
        badges = badges.filter(
            Q(recipient__icontains=search) |
            Q(program_line1__icontains=search) |
            Q(program_line2__icontains=search) |
            Q(credential_id__icontains=search) |
            Q(badge_no__icontains=search)
        )

    serializer = BadgeListSerializer(badges, many=True)
    return Response({
        'badges': serializer.data,
        'total': badges.count(),
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_detail(request, badge_id):
    """
    Get full badge detail including SVG.
    GET /api/badges/<id>/
    """
    badge = get_object_or_404(Badge, id=badge_id, issuer=request.user)
    serializer = BadgeSerializer(badge)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_by_credential(request, credential_id):
    """
    Get badge by credential_id.
    GET /api/badges/credential/<credential_id>/
    """
    badge = get_object_or_404(Badge, credential_id=credential_id, issuer=request.user)
    serializer = BadgeSerializer(badge)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_stats(request):
    """
    Get badge statistics.
    GET /api/badges/stats/
    """
    user = request.user
    badges = Badge.objects.filter(issuer=user)

    current_month = datetime.now().month
    current_year = datetime.now().year

    stats = {
        'total': badges.count(),
        'active': badges.filter(status='active').count(),
        'revoked': badges.filter(status='revoked').count(),
        'this_month': badges.filter(
            issue_date__month=current_month,
            issue_date__year=current_year
        ).count(),
    }

    return Response(stats, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_badge(request, credential_id):
    """
    Public endpoint to verify a badge.
    GET /api/badges/verify/<credential_id>/
    """
    try:
        badge = Badge.objects.get(credential_id=credential_id)
        serializer = BadgeSerializer(badge)
        return Response({
            'valid': badge.status == 'active',
            'message': 'Badge is valid' if badge.status == 'active' else 'Badge has been revoked',
            'badge': serializer.data,
        }, status=status.HTTP_200_OK)
    except Badge.DoesNotExist:
        return Response({
            'valid': False,
            'message': 'Badge not found',
        }, status=status.HTTP_404_NOT_FOUND)