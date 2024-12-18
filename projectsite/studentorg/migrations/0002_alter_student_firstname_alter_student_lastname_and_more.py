# Generated by Django 5.1.2 on 2024-11-06 07:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studentorg', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='firstname',
            field=models.CharField(max_length=25, verbose_name='First Name'),
        ),
        migrations.AlterField(
            model_name='student',
            name='lastname',
            field=models.CharField(max_length=25, verbose_name='Last Name'),
        ),
        migrations.AlterField(
            model_name='student',
            name='program',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='studentorg.program'),
        ),
    ]
