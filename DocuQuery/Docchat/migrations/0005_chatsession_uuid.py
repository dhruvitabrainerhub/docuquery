import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Docchat', '0004_rename_context_chatmessage_content'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chatmessage',
            name='session',
        ),
        migrations.DeleteModel(
            name='ChatSession',
        ),
        migrations.CreateModel(
            name='ChatSession',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='session',
            field=models.ForeignKey(
                default=None,
                on_delete=models.deletion.CASCADE,
                related_name='messages',
                to='Docchat.chatsession',
            ),
            preserve_default=False,
        ),
    ]
