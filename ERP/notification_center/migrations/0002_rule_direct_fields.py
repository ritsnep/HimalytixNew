from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notification_center', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationrule',
            name='direct_email',
            field=models.EmailField(blank=True, help_text='Fallback email when path resolution fails (for email channel).', max_length=254),
        ),
        migrations.AddField(
            model_name='notificationrule',
            name='direct_phone',
            field=models.CharField(blank=True, help_text='Fallback phone when path resolution fails (for SMS channel).', max_length=50),
        ),
        migrations.AddField(
            model_name='notificationrule',
            name='direct_user',
            field=models.ForeignKey(blank=True, help_text='Fallback user when path resolution fails.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_rules_as_recipient', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='notificationrule',
            name='fallback_to_request_user',
            field=models.BooleanField(default=True, help_text='Use request.user as last resort for in-app and Django messages.'),
        ),
    ]
