from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


# signals.py
# Place this file in your Django app directory (same folder as models.py)
# Then register it in your AppConfig (see apps.py addition below)

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Certificate, Badge


def _split_course_title(course: str):
    """Split a long course title across two lines for the badge."""
    if len(course) <= 26:
        return course.upper(), ''
    words = course.split()
    mid = (len(words) + 1) // 2
    line1 = ' '.join(words[:mid]).upper()
    line2 = ' '.join(words[mid:]).upper()
    return line1, line2


def _escape_xml(s: str) -> str:
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;')
             .replace("'", '&apos;'))


def generate_badge_svg(badge_data: dict) -> str:
    """
    Generate the SVG badge matching the CredentialPath shield design.
    badge_data keys: program_line1, program_line2, issuer_name, year
    """
    line1 = badge_data['program_line1']
    line2 = badge_data.get('program_line2', '')
    issuer = badge_data['issuer_name']
    year = badge_data['year']
    has_line2 = bool(line2.strip())

    issuer_box_y  = 358 if has_line2 else 345
    issuer_text_y = 384 if has_line2 else 371
    verified_y    = 428 if has_line2 else 415
    year_y        = 453 if has_line2 else 440

    line2_svg = (
        f'<text x="250" y="338" font-family="\'Arial Black\',Arial,sans-serif" '
        f'font-size="15.5" font-weight="700" fill="white" text-anchor="middle">'
        f'{_escape_xml(line2)}</text>'
    ) if has_line2 else ''

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 580" width="500" height="580">
  <defs>
    <linearGradient id="sg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4B52B5"/>
      <stop offset="100%" style="stop-color:#3A3F9E"/>
    </linearGradient>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B72C8"/>
      <stop offset="100%" style="stop-color:#5A5FB5"/>
    </linearGradient>
    <filter id="sh"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#1E2060" flood-opacity="0.4"/></filter>
  </defs>
  <path d="M250 10 C250 10,420 10,460 50 C490 80,490 130,490 160 C490 260,480 320,440 380 C400 440,330 490,250 560 C170 490,100 440,60 380 C20 320,10 260,10 160 C10 130,10 80,40 50 C80 10,250 10,250 10Z" fill="url(#bg)" filter="url(#sh)"/>
  <path d="M250 28 C250 28,408 28,444 65 C472 93,472 140,472 168 C472 261,462 318,424 376 C387 432,320 480,250 545 C180 480,113 432,76 376 C38 318,28 261,28 168 C28 140,28 93,56 65 C92 28,250 28,250 28Z" fill="url(#sg)"/>
  <path d="M250 44 C250 44,396 44,430 79 C456 105,456 150,456 176 C456 264,447 318,411 373 C376 426,312 472,250 532 C188 472,124 426,89 373 C53 318,44 264,44 176 C44 150,44 105,70 79 C104 44,250 44,250 44Z" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="2"/>
  <circle cx="250" cy="130" r="52" fill="none" stroke="rgba(255,255,255,0.85)" stroke-width="5"/>
  <g stroke="rgba(255,255,255,0.85)" stroke-width="5" stroke-linecap="round">
    <line x1="250" y1="63" x2="250" y2="76"/><line x1="250" y1="184" x2="250" y2="197"/>
    <line x1="183" y1="130" x2="196" y2="130"/><line x1="304" y1="130" x2="317" y2="130"/>
    <line x1="202" y1="83" x2="211" y2="92"/><line x1="289" y1="168" x2="298" y2="177"/>
    <line x1="298" y1="83" x2="289" y2="92"/><line x1="211" y1="168" x2="202" y2="177"/>
  </g>
  <circle cx="250" cy="118" r="14" fill="rgba(255,255,255,0.9)"/>
  <path d="M228 148 Q250 138 272 148 L272 160 Q250 154 228 160Z" fill="rgba(255,255,255,0.9)"/>
  <circle cx="222" cy="162" r="18" fill="#3A3F9E" stroke="rgba(255,255,255,0.9)" stroke-width="2.5"/>
  <polyline points="213,162 220,170 232,153" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="278" cy="162" r="15" fill="#3A3F9E" stroke="rgba(255,255,255,0.9)" stroke-width="2.5"/>
  <circle cx="278" cy="162" r="6" fill="none" stroke="white" stroke-width="2.5"/>
  <g stroke="white" stroke-width="2" stroke-linecap="round">
    <line x1="278" y1="149" x2="278" y2="152"/><line x1="278" y1="172" x2="278" y2="175"/>
    <line x1="265" y1="162" x2="268" y2="162"/><line x1="288" y1="162" x2="291" y2="162"/>
  </g>
  <text x="250" y="245" font-family="'Arial Black',Arial,sans-serif" font-size="38" font-weight="900" fill="white" text-anchor="middle" letter-spacing="2">COMPETENCE</text>
  <text x="250" y="270" font-family="'Arial Black',Arial,sans-serif" font-size="14" font-weight="700" fill="rgba(255,255,255,0.88)" text-anchor="middle" letter-spacing="3">ASSESSED &amp; VERIFIED</text>
  <line x1="95" y1="287" x2="405" y2="287" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>
  <text x="250" y="316" font-family="'Arial Black',Arial,sans-serif" font-size="15.5" font-weight="700" fill="white" text-anchor="middle">{_escape_xml(line1)}</text>
  {line2_svg}
  <rect x="82" y="{issuer_box_y}" width="336" height="44" rx="6" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
  <text x="250" y="{issuer_text_y}" font-family="'Arial Black',Arial,sans-serif" font-size="13.5" font-weight="800" fill="white" text-anchor="middle" letter-spacing="0.5">ISSUED BY {_escape_xml(issuer.upper())}</text>
  <text x="250" y="{verified_y}" font-family="Arial,sans-serif" font-size="12" fill="rgba(255,255,255,0.72)" text-anchor="middle">Verified By CredentialPath</text>
  <text x="250" y="{year_y}" font-family="'Arial Black',Arial,sans-serif" font-size="20" font-weight="900" fill="white" text-anchor="middle">{_escape_xml(year)}</text>
</svg>"""


@receiver(post_save, sender=Certificate)
def auto_create_or_update_badge(sender, instance, created, **kwargs):
    """
    Signal handler: automatically creates or updates a Badge whenever
    a Competence certificate is saved.

    - On CREATE: generates a new Badge with SVG
    - On UPDATE (status change to 'revoked'): syncs badge status
    - Non-competence certificates are ignored
    """
    if instance.certificate_type != 'Competence':
        return

    line1, line2 = _split_course_title(instance.course)
    year = str(instance.issue_date.year) if instance.issue_date else ''

    svg_data = {
        'program_line1': line1,
        'program_line2': line2,
        'issuer_name': instance.issuer_name,
        'year': year,
    }
    badge_svg = generate_badge_svg(svg_data)

    badge_defaults = {
        'issuer': instance.issuer,
        'recipient': instance.recipient,
        'program_line1': line1,
        'program_line2': line2,
        'issuer_name': instance.issuer_name,
        'issue_date': instance.issue_date,
        'year': year,
        'badge_svg': badge_svg,
        'verification_link': instance.verification_link,
        'status': instance.status,  # stays in sync with certificate
    }

    badge, badge_created = Badge.objects.update_or_create(
        certificate=instance,
        defaults=badge_defaults,
    )

    # Also keep badge_no / credential_id in sync on first creation
    if badge_created:
        badge.badge_no = instance.certificate_no
        badge.credential_id = instance.credential_id
        badge.save(update_fields=['badge_no', 'credential_id'])


@receiver(post_delete, sender=Certificate)
def auto_delete_badge(sender, instance, **kwargs):
    """
    Signal handler: deletes the linked Badge when a Certificate is deleted.
    The OneToOneField cascade handles this automatically, but this is
    kept explicit for clarity and in case cascade is ever changed.
    """
    try:
        if hasattr(instance, 'badge') and instance.badge:
            instance.badge.delete()
    except Badge.DoesNotExist:
        pass