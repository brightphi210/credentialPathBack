import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=255)
    full_name = models.CharField(max_length=255)
    business_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    email_verification_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.email


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    company_bio = models.TextField(blank=True)
    company_address = models.CharField(max_length=500, blank=True)
    company_phone = models.CharField(max_length=20, blank=True)
    linkedin_handle = models.URLField(max_length=500, blank=True)
    twitter_handle = models.CharField(max_length=100, blank=True)
    facebook_handle = models.CharField(max_length=100, blank=True)
    instagram_handle = models.CharField(max_length=100, blank=True)
    default_signatory_name = models.CharField(max_length=255, blank=True)
    default_signatory_title = models.CharField(max_length=255, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    # ── NEW: signatory signature image (compulsory for certificate issuance) ──
    signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.email}'s Profile"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _company_slug(name: str) -> str:
    """
    Extract up to 2 uppercase alphabetic characters from the company/issuer name
    to use as a short prefix in the certificate number.

    Examples:
        "TechAcademy Ltd."  → "TA"
        "Acme Training Co." → "AT"
        "ISO Global"        → "IG"
        "XYZ"               → "XY"
    """
    import re
    # Keep only letters, split into words, take first letter of each word
    words = re.findall(r'[A-Za-z]+', name)
    if not words:
        return 'XX'
    # Use first letters of first two words (or repeat first if only one word)
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _next_cert_sequence(issuer) -> int:
    """
    Return the next sequential integer for certificates issued by this issuer.
    Counts all existing certificates (regardless of status) and adds 1.
    """
    return Certificate.objects.filter(issuer=issuer).count() + 1


def generate_certificate_no(issuer) -> str:
    """
    Build a short, human-readable, unique certificate number:

        {2-CHAR-SLUG}{YY}{MM}{DD}{2-DIGIT-SEQ}

    Total length: 12 characters (no separators), e.g.:
        TA260408-01  →  'TA26040801'
        IG260408-01  →  'IG26040801'

    Format breakdown:
        TA   = 2-char company slug
        26   = 2-digit year
        04   = 2-digit month
        08   = 2-digit day
        01   = 2-digit sequence (resets context is per issuer+day if needed)
    """
    from django.utils import timezone
    slug = _company_slug(issuer.business_name or issuer.full_name)
    now = timezone.now()
    date_str = now.strftime('%y%m%d')   # e.g. '260408'
    seq = _next_cert_sequence(issuer)
    cert_no = f"{slug}{date_str}{seq:02d}"   # e.g. 'TA26040801'

    # Safety: race-condition guard — increment seq until unique
    while Certificate.objects.filter(certificate_no=cert_no).exists():
        seq += 1
        cert_no = f"{slug}{date_str}{seq:02d}"

    return cert_no


def generate_credential_id() -> str:
    """
    Generate a backend-only opaque credential ID (UUID4 hex, uppercase).
    Never shown to end users; used internally.
    """
    return uuid.uuid4().hex.upper()


# ─────────────────────────────────────────────────────────────────────────────
# CERTIFICATE MODEL
# ─────────────────────────────────────────────────────────────────────────────

class Certificate(models.Model):
    CERTIFICATE_TYPES = (
        ('Completion', 'Completion'),
        ('Competence', 'Competence'),
        ('Attendance', 'Attendance'),
    )
    DELIVERY_MODES = (
        ('Online', 'Online'),
        ('Blended', 'Blended'),
        ('In-Person', 'In-Person'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    )

    issuer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_certificates')

    # certificate_no: human-readable, shown on certificate, used for public verification
    certificate_no = models.CharField(max_length=150, unique=True, blank=True)

    # credential_id: backend-only opaque UUID — never shown to end users
    credential_id = models.CharField(max_length=64, unique=True, blank=True)

    recipient = models.CharField(max_length=255)
    course = models.CharField(max_length=500)
    program = models.CharField(max_length=255, blank=True)
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES, default='Completion')
    phrase = models.CharField(max_length=255, blank=True)
    issue_date = models.DateField()
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODES, blank=True, null=True)
    competence_result = models.CharField(max_length=100, blank=True, null=True)
    competence_expiry_date = models.DateField(blank=True, null=True)
    hours_cpd = models.CharField(max_length=50, blank=True, null=True)
    signatory_name = models.CharField(max_length=255)
    signatory_title = models.CharField(max_length=255)
    issuer_name = models.CharField(max_length=255)
    issuer_location = models.CharField(max_length=500)

    # verification_link uses certificate_no (public-facing)
    verification_link = models.URLField(max_length=500, blank=True)
    # qr_code encodes the full frontend verification URL for this certificate
    qr_code = models.URLField(max_length=500, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['certificate_no']),
            models.Index(fields=['credential_id']),
            models.Index(fields=['issuer', 'status']),
        ]

    def __str__(self):
        return f"{self.certificate_no} - {self.recipient}"

    def generate_verification_link(self) -> str:
        """
        Frontend verification URL — uses certificate_no so recipients can
        type or share it easily.
        e.g. https://credentialpath.io/verify/TA26040801/
        """
        return f"https://credentialpath.io/verify/{self.certificate_no}/"

    def generate_qr_code(self) -> str:
        """
        QR code encodes the full frontend verification URL for THIS certificate
        so scanning the QR takes the verifier directly to the result page.
        """
        link = self.verification_link or self.generate_verification_link()
        return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={link}"

    def save(self, *args, **kwargs):
        # Auto-generate certificate_no on creation only
        if not self.certificate_no:
            self.certificate_no = generate_certificate_no(self.issuer)

        # Auto-generate credential_id on creation only
        if not self.credential_id:
            cid = generate_credential_id()
            while Certificate.objects.filter(credential_id=cid).exists():
                cid = generate_credential_id()
            self.credential_id = cid

        # Verification link and QR code
        if not self.verification_link:
            self.verification_link = self.generate_verification_link()
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()

        # Auto-set phrase from type
        if not self.phrase:
            phrase_map = {
                'Completion': 'has successfully completed',
                'Competence': 'has demonstrated competence in',
                'Attendance': 'has attended',
            }
            self.phrase = phrase_map.get(self.certificate_type, 'has successfully completed')

        super().save(*args, **kwargs)


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('certificate_created', 'Certificate Created'),
        ('certificate_revoked', 'Certificate Revoked'),
        ('certificate_deleted', 'Certificate Deleted'),
        ('certificate_updated', 'Certificate Updated'),
        ('bulk_upload', 'Bulk Upload'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class Badge(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    )
    issuer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_badges')
    certificate = models.OneToOneField(
        Certificate, on_delete=models.CASCADE,
        related_name='badge', null=True, blank=True,
    )
    badge_no = models.CharField(max_length=150, unique=True)
    credential_id = models.CharField(max_length=64, unique=True)
    recipient = models.CharField(max_length=255)
    program_line1 = models.CharField(max_length=255)
    program_line2 = models.CharField(max_length=255, blank=True)
    issuer_name = models.CharField(max_length=255)
    issue_date = models.DateField()
    year = models.CharField(max_length=4)
    badge_svg = models.TextField(blank=True)
    verification_link = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['issuer', 'status']),
            models.Index(fields=['credential_id']),
        ]

    def __str__(self):
        return f"Badge: {self.badge_no} – {self.recipient}"