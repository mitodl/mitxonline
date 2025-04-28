from django.db import migrations


def update_usernames_to_email(apps, schema_editor):
    """Update usernames to match user email addresses"""
    User = apps.get_model("users", "User")

    # Update usernames to match emails but truncate at max length
    # Get max_length from username field
    max_length = User._meta.get_field('username').max_length  # noqa: SLF001
    
    users = User.objects.all()
    for user in users:
        new_username = user.email[:max_length]
        user.username = new_username
        user.save()


def reverse_migration(apps, schema_editor):
    """No-op reverse migration"""


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0026_alter_user_is_active"),
    ]

    operations = [
        migrations.RunPython(update_usernames_to_email, reverse_code=reverse_migration),
    ]
