# Create your models here.
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
    is_active = models.BooleanField(default=False)  # Changed to False - users must verify email
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
    
    # Certificate defaults
    default_signatory_name = models.CharField(max_length=255, blank=True)
    default_signatory_title = models.CharField(max_length=255, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.email}'s Profile"
    

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
    
    # User who issued the certificate
    issuer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_certificates')
    
    # Certificate Details
    certificate_no = models.CharField(max_length=100, unique=True)
    credential_id = models.CharField(max_length=100, unique=True)
    
    # Recipient Information
    recipient = models.CharField(max_length=255)
    
    # Course/Program Information
    course = models.CharField(max_length=500)
    program = models.CharField(max_length=255, blank=True)
    
    # Certificate Type
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES, default='Completion')
    phrase = models.CharField(max_length=255, blank=True)
    
    # Issue Information
    issue_date = models.DateField()
    
    # Delivery and Additional Info
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODES, blank=True, null=True)
    competence_result = models.CharField(max_length=100, blank=True, null=True)
    competence_expiry_date = models.DateField(blank=True, null=True)
    hours_cpd = models.CharField(max_length=50, blank=True, null=True)  # New field
    
    # Signatory Information
    signatory_name = models.CharField(max_length=255)
    signatory_title = models.CharField(max_length=255)
    
    # Issuer Details (auto-filled from user profile)
    issuer_name = models.CharField(max_length=255)
    issuer_location = models.CharField(max_length=500)
    
    # Verification
    verification_link = models.URLField(max_length=500, blank=True)
    qr_code = models.URLField(max_length=500, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Timestamps
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
    
    def generate_verification_link(self):
        return f"https://credentialpath.com/verify/"
    
    def generate_qr_code(self):
        link = self.verification_link or self.generate_verification_link()
        return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={link}"
    
    def save(self, *args, **kwargs):
        # Auto-generate verification link and QR code if not set
        if not self.verification_link:
            self.verification_link = self.generate_verification_link()
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        
        # Auto-set phrase based on certificate type if not set
        if not self.phrase:
            if self.certificate_type == 'Completion':
                self.phrase = 'has successfully completed'
            elif self.certificate_type == 'Competence':
                self.phrase = 'has demonstrated competence in'
            elif self.certificate_type == 'Attendance':
                self.phrase = 'has attended'
        
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
    """
    Auto-generated when a Competence certificate is issued.
    Stores the badge SVG and links back to the issuing certificate and recipient user context.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    )

    # The user (issuer) who owns/issued this badge
    issuer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='issued_badges'
    )

    # Linked certificate (one-to-one: one badge per competence cert)
    certificate = models.OneToOneField(
        Certificate,
        on_delete=models.CASCADE,
        related_name='badge',
        null=True,
        blank=True
    )

    # Badge details (mirrored from certificate for quick access)
    badge_no = models.CharField(max_length=100, unique=True)          # mirrors certificate_no
    credential_id = models.CharField(max_length=100, unique=True)     # mirrors credential_id
    recipient = models.CharField(max_length=255)
    program_line1 = models.CharField(max_length=255)
    program_line2 = models.CharField(max_length=255, blank=True)
    issuer_name = models.CharField(max_length=255)
    issue_date = models.DateField()
    year = models.CharField(max_length=4)

    # The generated SVG content
    badge_svg = models.TextField(blank=True)

    # Verification
    verification_link = models.URLField(max_length=500, blank=True)

    # Status mirrors the linked certificate
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