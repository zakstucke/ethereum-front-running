# Generated by Django 3.2.13 on 2022-04-30 21:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('primary', '0003_auto_20220430_1719'),
    ]

    operations = [
        migrations.AddField(
            model_name='experimentlog',
            name='agent_start_balance',
            field=models.DecimalField(decimal_places=18, default=0, max_digits=50),
        ),
        migrations.AddField(
            model_name='experimentlog',
            name='attacker_start_balance',
            field=models.DecimalField(decimal_places=18, default=0, max_digits=50),
        ),
    ]