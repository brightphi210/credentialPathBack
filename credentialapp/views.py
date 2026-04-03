import datetime
from rest_framework import status, generics, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import Badge, Certificate, Notification, User, UserProfile
from .serializers import BadgeSerializer, BadgeListSerializer
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChangePasswordSerializer, UpdateProfileSerializer, UserProfileSerializer,
    CertificateSerializer, CreateCertificateSerializer,
    BulkCertificateSerializer, UpdateCertificateSerializer,
    RevokeCertificateSerializer, NotificationSerializer,
)
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count

from .utils import send_verification_email, send_welcome_email, is_otp_valid, create_notification


# ==================== AUTH VIEWS ====================

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        email_sent = send_verification_email(user, request)
        return Response({
            'message': 'Registration successful! Please check your email for the verification code.',
            'email_sent': email_sent,
            'email': user.email,
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_otp(request):
    email = request.data.get('email')
    otp = request.data.get('otp')

    if not email or not otp:
        return Response({'error': 'Email and OTP code are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.is_email_verified:
            return Response({'message': 'Email already verified. You can login now.', 'already_verified': True})

        if not is_otp_valid(user):
            return Response({'error': 'OTP has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.email_verification_otp != otp:
            return Response({'error': 'Invalid OTP code. Please check and try again.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_email_verified = True
        user.is_active = True
        user.email_verification_otp = None
        user.otp_created_at = None
        user.save()
        send_welcome_email(user)

        return Response({'message': 'Email verified successfully! You can now login.', 'verified': True})

    except User.DoesNotExist:
        return Response({'error': 'No account found with this email address'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_email_verified:
        return Response({
            'error': 'Please verify your email before logging in. Check your inbox for the OTP code.',
            'email_verified': False,
            'email': email,
        }, status=status.HTTP_403_FORBIDDEN)

    user = authenticate(email=email, password=password)
    if user is None:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        return Response({'error': 'Account is disabled. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    user_serializer = UserSerializer(user, context={'request': request})

    return Response({
        'message': 'Login successful',
        'user': user_serializer.data,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    serializer = UserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    user = request.user
    profile = user.profile

    if 'full_name' in request.data:
        user.full_name = request.data['full_name']
    if 'business_name' in request.data:
        user.business_name = request.data['business_name']
    user.save()

    serializer = UpdateProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    user_serializer = UserSerializer(user, context={'request': request})
    return Response({'message': 'Profile updated successfully', 'user': user_serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not user.check_password(serializer.validated_data['old_password']):
        return Response({'error': 'Old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    return Response({'message': 'Password changed successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Logout successful'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_otp(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.is_email_verified:
            return Response({'message': 'Email already verified. You can login now.'})

        email_sent = send_verification_email(user, request)
        if email_sent:
            return Response({'message': 'A new verification code has been sent to your email.'})
        return Response({'error': 'Failed to send email. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except User.DoesNotExist:
        return Response({'error': 'No account found with this email address'}, status=status.HTTP_404_NOT_FOUND)


# ==================== CERTIFICATE VIEWS ====================

class CertificateListView(generics.ListAPIView):
    """GET /api/certificates/"""
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['recipient', 'course', 'certificate_no']
    ordering_fields = ['created_at', 'issue_date', 'recipient']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Certificate.objects.filter(issuer=self.request.user)

        status_filter = self.request.query_params.get('status', None)
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        cert_type = self.request.query_params.get('type', None)
        if cert_type:
            queryset = queryset.filter(certificate_type=cert_type)

        program = self.request.query_params.get('program', None)
        if program:
            queryset = queryset.filter(program=program)

        return queryset


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_single_certificate(request):
    """
    POST /api/certificates/create/

    The client does NOT send certificate_no or credential_id — both are
    auto-generated by Certificate.save().
    """
    user = request.user
    serializer = CreateCertificateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    certificate = Certificate.objects.create(
        issuer=user,
        issuer_name=user.business_name or user.full_name,
        issuer_location=user.profile.company_address,
        **serializer.validated_data,
    )

    create_notification(
        user=user,
        notification_type='certificate_created',
        title='Certificate Issued',
        message=f'Certificate for {certificate.recipient} ({certificate.certificate_no}) has been successfully issued.',
        certificate=certificate,
    )

    return Response({
        'message': 'Certificate created successfully',
        'certificate': CertificateSerializer(certificate).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bulk_certificates(request):
    """POST /api/certificates/bulk-create/"""
    serializer = BulkCertificateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    certificates = serializer.save()

    create_notification(
        user=request.user,
        notification_type='bulk_upload',
        title='Bulk Upload Complete',
        message=f'{len(certificates)} certificates have been successfully created from your upload.',
        certificate=None,
    )

    return Response({
        'message': f'{len(certificates)} certificates created successfully',
        'certificates': CertificateSerializer(certificates, many=True).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate_detail(request, certificate_id):
    """GET /api/certificates/<id>/"""
    certificate = get_object_or_404(Certificate, id=certificate_id, issuer=request.user)
    return Response(CertificateSerializer(certificate).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_certificate(request, certificate_id):
    """PUT/PATCH /api/certificates/<id>/update/"""
    certificate = get_object_or_404(Certificate, id=certificate_id, issuer=request.user)
    serializer = UpdateCertificateSerializer(certificate, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    create_notification(
        user=request.user,
        notification_type='certificate_updated',
        title='Certificate Updated',
        message=f'Certificate {certificate.certificate_no} for {certificate.recipient} has been updated.',
        certificate=certificate,
    )

    return Response({
        'message': 'Certificate updated successfully',
        'certificate': CertificateSerializer(certificate).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_certificate(request, certificate_id):
    """POST /api/certificates/<id>/revoke/"""
    certificate = get_object_or_404(Certificate, id=certificate_id, issuer=request.user)

    if certificate.status == 'revoked':
        return Response({'error': 'Certificate is already revoked'}, status=status.HTTP_400_BAD_REQUEST)

    certificate.status = 'revoked'
    certificate.save()

    create_notification(
        user=request.user,
        notification_type='certificate_revoked',
        title='Certificate Revoked',
        message=f'Certificate {certificate.certificate_no} has been revoked as requested.',
        certificate=certificate,
    )

    return Response({
        'message': 'Certificate revoked successfully',
        'certificate': CertificateSerializer(certificate).data,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_certificate(request, certificate_id):
    """DELETE /api/certificates/<id>/delete/"""
    certificate = get_object_or_404(Certificate, id=certificate_id, issuer=request.user)
    cert_no = certificate.certificate_no
    recipient = certificate.recipient
    certificate.delete()

    create_notification(
        user=request.user,
        notification_type='certificate_deleted',
        title='Certificate Deleted',
        message=f'Certificate {cert_no} for {recipient} has been permanently deleted.',
        certificate=None,
    )

    return Response({'message': 'Certificate deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate_stats(request):
    """GET /api/certificates/stats/"""
    user = request.user
    certificates = Certificate.objects.filter(issuer=user)
    now = datetime.datetime.now()

    stats = {
        'total': certificates.count(),
        'active': certificates.filter(status='active').count(),
        'revoked': certificates.filter(status='revoked').count(),
        'this_month': certificates.filter(
            issue_date__month=now.month, issue_date__year=now.year
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
        ),
    }
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_monthly_certificate_data(request):
    """GET /api/certificates/monthly-data/"""
    user = request.user
    current_date = datetime.datetime.now()
    monthly_data = []

    for i in range(5, -1, -1):
        target_date = current_date - datetime.timedelta(days=30 * i)
        count = Certificate.objects.filter(
            issuer=user,
            issue_date__month=target_date.month,
            issue_date__year=target_date.year,
        ).count()
        monthly_data.append({'month': target_date.strftime('%b'), 'total': count})

    return Response(monthly_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_activity(request):
    """GET /api/certificates/recent-activity/"""
    user = request.user
    limit = int(request.query_params.get('limit', 5))
    recent_certificates = Certificate.objects.filter(issuer=user).order_by('-created_at')[:limit]

    activities = []
    for cert in recent_certificates:
        time_diff = datetime.datetime.now() - cert.created_at.replace(tzinfo=None)
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
            'certificate_no': cert.certificate_no,
            'date': time_ago,
            'status': cert.status,
            'created_at': cert.created_at.isoformat(),
        })

    return Response(activities)


# ==================== PUBLIC VERIFICATION VIEWS ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def search_certificate(request):
    """
    POST /api/verify/search/
    Body: { "query": "TECHACADEMY-2026-00001" }

    Searches by certificate_no (the human-readable number shown on the certificate).
    Credential ID is backend-only and is NOT searched here.
    """
    query = request.data.get('query', '').strip()

    if not query:
        return Response({'status': 'error', 'message': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Search only by certificate_no — the public-facing identifier
        try:
            certificate = Certificate.objects.get(certificate_no=query)
        except Certificate.DoesNotExist:
            # Fallback: case-insensitive partial match on certificate_no
            certificates = Certificate.objects.filter(certificate_no__iexact=query)
            if certificates.exists():
                certificate = certificates.first()
            else:
                return Response({
                    'status': 'error',
                    'message': 'Certificate not found',
                    'detail': 'No certificate matches your query. Please check the certificate number.',
                }, status=status.HTTP_404_NOT_FOUND)

        serializer = CertificateSerializer(certificate)
        return Response({
            'status': 'verified',
            'message': 'Certificate found and verified successfully',
            'data': serializer.data,
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': 'An error occurred during verification',
            'detail': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_certificate(request, certificate_no):
    """
    GET /api/verify/<certificate_no>/

    Public verification endpoint — uses certificate_no (human-readable),
    not the internal credential_id.
    """
    try:
        certificate = Certificate.objects.get(certificate_no=certificate_no)
        serializer = CertificateSerializer(certificate)
        return Response({
            'status': 'verified' if certificate.status == 'active' else 'revoked',
            'message': 'Certificate is valid' if certificate.status == 'active' else 'Certificate has been revoked',
            'data': serializer.data,
        })

    except Certificate.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Certificate not found',
            'detail': f'No certificate found with number: {certificate_no}',
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': 'An error occurred during verification',
            'detail': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== NOTIFICATION VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """GET /api/notifications/"""
    user = request.user
    notifications = Notification.objects.filter(user=user)

    notification_type = request.query_params.get('type', None)
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)

    limit = request.query_params.get('limit', None)
    if limit:
        try:
            notifications = notifications[:int(limit)]
        except ValueError:
            pass

    serializer = NotificationSerializer(notifications, many=True)
    return Response({'notifications': serializer.data, 'total': notifications.count()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """DELETE /api/notifications/<id>/delete/"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    return Response({'message': 'Notification deleted successfully'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    """DELETE /api/notifications/clear-all/"""
    deleted_count = Notification.objects.filter(user=request.user).delete()[0]
    return Response({'message': f'{deleted_count} notifications cleared successfully'})


# ==================== BADGE VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badges(request):
    """GET /api/badges/"""
    user = request.user
    badges = Badge.objects.filter(issuer=user)

    status_filter = request.query_params.get('status', None)
    if status_filter and status_filter != 'all':
        badges = badges.filter(status=status_filter)

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
    return Response({'badges': serializer.data, 'total': badges.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_detail(request, badge_id):
    """GET /api/badges/<id>/"""
    badge = get_object_or_404(Badge, id=badge_id, issuer=request.user)
    return Response(BadgeSerializer(badge).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_by_credential(request, credential_id):
    """GET /api/badges/credential/<credential_id>/"""
    badge = get_object_or_404(Badge, credential_id=credential_id, issuer=request.user)
    return Response(BadgeSerializer(badge).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_badge_stats(request):
    """GET /api/badges/stats/"""
    user = request.user
    badges = Badge.objects.filter(issuer=user)
    now = datetime.datetime.now()

    stats = {
        'total': badges.count(),
        'active': badges.filter(status='active').count(),
        'revoked': badges.filter(status='revoked').count(),
        'this_month': badges.filter(
            issue_date__month=now.month, issue_date__year=now.year
        ).count(),
    }
    return Response(stats)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_badge(request, credential_id):
    """GET /api/badges/verify/<credential_id>/"""
    try:
        badge = Badge.objects.get(credential_id=credential_id)
        return Response({
            'valid': badge.status == 'active',
            'message': 'Badge is valid' if badge.status == 'active' else 'Badge has been revoked',
            'badge': BadgeSerializer(badge).data,
        })
    except Badge.DoesNotExist:
        return Response({'valid': False, 'message': 'Badge not found'}, status=status.HTTP_404_NOT_FOUND)