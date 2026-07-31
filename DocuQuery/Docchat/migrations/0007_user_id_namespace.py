from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Docchat', '0006_documents_status_documents_task_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='documents',
            name='user_id',
            field=models.CharField(default='default', max_length=255),
        ),
        migrations.AddField(
            model_name='chatsession',
            name='user_id',
            field=models.CharField(default='default', max_length=255),
        ),
    ]
