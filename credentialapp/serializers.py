import datetime
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import Notification, User, UserProfile, Certificate, Badge


class UserProfileSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    company_logo_url = serializers.SerializerMethodField()
    # ── NEW ──────────────────────────────────────────────────────────────────
    signature_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'profile_image', 'profile_image_url', 'company_bio', 'company_address', 'company_phone',
            'linkedin_handle', 'twitter_handle', 'facebook_handle', 'instagram_handle',
            'default_signatory_name', 'default_signatory_title',
            'company_logo', 'company_logo_url',
            # ── NEW ──────────────────────────────────────────────────────────
            'signature', 'signature_url',
        ]

    def get_profile_image_url(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
        return None

    def get_company_logo_url(self, obj):
        if obj.company_logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.company_logo.url)
        return None

    # ── NEW ──────────────────────────────────────────────────────────────────
    def get_signature_url(self, obj):
        if obj.signature:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.signature.url)
        return None


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'business_name', 'date_joined', 'profile']
        read_only_fields = ['id', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['email', 'full_name', 'business_name', 'password', 'password2']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            business_name=validated_data.get('business_name', '')
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs


class UpdateProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(required=False)
    company_logo = serializers.ImageField(required=False)
    # ── NEW ──────────────────────────────────────────────────────────────────
    signature = serializers.ImageField(required=False)
    company_bio = serializers.CharField(required=False, allow_blank=True)
    company_address = serializers.CharField(required=False, allow_blank=True)
    company_phone = serializers.CharField(required=False, allow_blank=True)
    linkedin_handle = serializers.URLField(required=False, allow_blank=True)
    twitter_handle = serializers.CharField(required=False, allow_blank=True)
    facebook_handle = serializers.CharField(required=False, allow_blank=True)
    instagram_handle = serializers.CharField(required=False, allow_blank=True)
    default_signatory_name = serializers.CharField(required=False, allow_blank=True)
    default_signatory_title = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UserProfile
        fields = [
            'profile_image', 'company_bio', 'company_address', 'company_phone',
            'linkedin_handle', 'twitter_handle', 'facebook_handle', 'instagram_handle',
            'default_signatory_name', 'default_signatory_title',
            'company_logo',
            # ── NEW ──────────────────────────────────────────────────────────
            'signature',
        ]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ─────────────────────────────────────────────────────────────────────────────
# CERTIFICATE SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class CertificateSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for returning certificate data.
    Returns certificate_no (human-readable) but NOT credential_id —
    credential_id is a backend-only identifier.
    """
    issuer_email = serializers.EmailField(source='issuer.email', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id', 'certificate_no', 'recipient', 'course',
            'program', 'certificate_type', 'phrase', 'issue_date',
            'delivery_mode', 'competence_result', 'competence_expiry_date', 'hours_cpd',
            'signatory_name', 'signatory_title', 'issuer_name', 'issuer_location',
            'verification_link', 'qr_code', 'status', 'created_at', 'updated_at',
            'issuer_email',
        ]
        read_only_fields = [
            'id', 'certificate_no', 'verification_link', 'qr_code',
            'created_at', 'updated_at',
        ]


class CreateCertificateSerializer(serializers.ModelSerializer):
    """
    Input serializer for creating a single certificate.
    certificate_no and credential_id are auto-generated and must not be supplied by the client.
    """

    class Meta:
        model = Certificate
        fields = [
            'recipient', 'course', 'program', 'certificate_type', 'phrase',
            'issue_date', 'delivery_mode', 'competence_result',
            'competence_expiry_date', 'hours_cpd',
            'signatory_name', 'signatory_title',
        ]

    def validate_issue_date(self, value):
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
                try:
                    return datetime.datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise serializers.ValidationError("Date has wrong format. Use YYYY-MM-DD format.")
        return value

    def validate_competence_expiry_date(self, value):
        if not value:
            return None
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
                try:
                    return datetime.datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise serializers.ValidationError("Date has wrong format. Use YYYY-MM-DD format.")
        return value


class BulkCertificateSerializer(serializers.Serializer):
    """
    Input serializer for creating multiple certificates at once.
    Each row uses CreateCertificateSerializer — no certificate_no or credential_id.
    """
    certificates = CreateCertificateSerializer(many=True)

    def create(self, validated_data):
        user = self.context['request'].user
        certificates_data = validated_data['certificates']

        certificates = []
        for cert_data in certificates_data:
            certificate = Certificate.objects.create(
                issuer=user,
                issuer_name=user.business_name or user.full_name,
                issuer_location=user.profile.company_address,
                **cert_data
            )
            certificates.append(certificate)

        return certificates


class UpdateCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = [
            'recipient', 'course', 'program', 'certificate_type',
            'issue_date', 'delivery_mode', 'competence_result',
            'competence_expiry_date', 'hours_cpd', 'signatory_name', 'signatory_title'
        ]


class RevokeCertificateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'type_display', 'title',
            'message', 'certificate', 'created_at', 'timestamp'
        ]
        read_only_fields = ['id', 'created_at']

    def get_timestamp(self, obj):
        # ✅ FIXED: use timezone.now() so both datetimes are timezone-aware — no more crash
        time_diff = timezone.now() - obj.created_at

        if time_diff.days > 0:
            if time_diff.days == 1:
                return "1 day ago"
            elif time_diff.days < 7:
                return f"{time_diff.days} days ago"
            elif time_diff.days < 30:
                weeks = time_diff.days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            else:
                months = time_diff.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
        elif time_diff.seconds // 3600 > 0:
            hours = time_diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            minutes = time_diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago" if minutes > 0 else "just now"


# ─────────────────────────────────────────────────────────────────────────────
# BADGE SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class BadgeSerializer(serializers.ModelSerializer):
    issuer_email = serializers.EmailField(source='issuer.email', read_only=True)
    certificate_no_ref = serializers.CharField(source='certificate.certificate_no', read_only=True)

    class Meta:
        model = Badge
        fields = [
            'id', 'badge_no', 'credential_id', 'recipient',
            'program_line1', 'program_line2', 'issuer_name',
            'issue_date', 'year', 'badge_svg', 'verification_link',
            'status', 'created_at', 'updated_at',
            'issuer_email', 'certificate_no_ref',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BadgeListSerializer(serializers.ModelSerializer):
    issuer_email = serializers.EmailField(source='issuer.email', read_only=True)

    class Meta:
        model = Badge
        fields = [
            'id', 'badge_no', 'credential_id', 'recipient',
            'program_line1', 'program_line2', 'issuer_name',
            'issue_date', 'year', 'verification_link',
            'status', 'created_at', 'issuer_email',
        ]
        read_only_fields = ['id', 'created_at']