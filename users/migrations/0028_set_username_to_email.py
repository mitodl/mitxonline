from django.db import migrations


def update_usernames_to_email(apps, schema_editor):
    """Update usernames to match user email addresses using bulk updates"""
    User = apps.get_model("users", "User")

    # Update usernames to match emails but truncate at max length
    max_length = User._meta.get_field("username").max_length  # noqa: SLF001

    batch_size = 1000
    users = User.objects.all()
    total_users = users.count()

    for start in range(0, total_users, batch_size):
        batch = users[start : start + batch_size]
        updates = []
        for user in batch:
            new_username = user.email[:max_length]
            updates.append(User(id=user.id, username=new_username))
        User.objects.bulk_update(updates, ["username"])


def reverse_migration(apps, schema_editor):
    """No-op reverse migration"""


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0027_alter_user_username"),
    ]

    operations = [
        migrations.RunPython(update_usernames_to_email, reverse_code=reverse_migration),
    ]
