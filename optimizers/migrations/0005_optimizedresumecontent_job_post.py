# Generated by Django 5.0 on 2024-02-01 16:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimizers", "0004_remove_jobpost_description_remove_jobpost_title_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="optimizedresumecontent",
            name="job_post",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="optimizers.jobpost",
            ),
        ),
    ]