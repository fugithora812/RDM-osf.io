# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-05-01 19:24
from __future__ import unicode_literals

from django.conf import settings
from django.core.management.sql import emit_post_migrate_signal
import django_extensions.db.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import osf.models.validators
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0104_merge_20180524_1257'),
    ]

    operations = [
        migrations.RenameModel('PreprintService', 'Preprint'),
        migrations.CreateModel(
            name='PreprintLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_id', models.CharField(db_index=True, default=osf.models.base.generate_object_id, max_length=24, unique=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('action', models.CharField(db_index=True, max_length=255)),
                ('params', osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(default=dict)),
                ('should_hide', models.BooleanField(default=False)),
                ('foreign_user', models.CharField(blank=True, max_length=255, null=True)),
                ('preprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='osf.Preprint')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='preprint_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
            },
        ),

        migrations.CreateModel(
            name='PreprintContributor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visible', models.BooleanField(default=False)),
                ('preprint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='osf.Preprint')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL))
            ],
        ),
        migrations.AlterModelOptions(
            name='preprint',
            options={'permissions': (('osf_admin_view_preprint', 'Can view preprint details in the admin app.'), ('read_preprint', 'Can read the preprint'), ('write_preprint', 'Can write the preprint'), ('admin_preprint', 'Can manage the preprint'))},
        ),
        migrations.AddField(
            model_name='preprint',
            name='region',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='addons_osfstorage.Region'),
        ),
        migrations.AddField(
            model_name='preprint',
            name='root_folder',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='preprint_object', to='osf.OsfStorageFolder'),
        ),
        migrations.AddField(
            model_name='preprint',
            name='primary_file',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='preprint', to='osf.OsfStorageFile'),
        ),
        migrations.AlterField(
            model_name='preprint',
            name='provider',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='preprints', to='osf.PreprintProvider'),
        ),
        migrations.AlterField(
            model_name='preprint',
            name='subjects',
            field=models.ManyToManyField(blank=True, related_name='preprints', to='osf.Subject'),
        ),
        migrations.AddField(
            model_name='preprint',
            name='creator',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='preprints_created', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='preprint',
            name='date_last_reported',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, db_index=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='reports',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(blank=True, default=dict, encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder, validators=[osf.models.spam._validate_reports]),
        ),
        migrations.AddField(
            model_name='preprint',
            name='spam_data',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(blank=True, default=dict, encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder),
        ),
        migrations.AddField(
            model_name='preprint',
            name='spam_pro_tip',
            field=models.CharField(blank=True, default=None, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='spam_status',
            field=models.IntegerField(blank=True, db_index=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='is_public',
            field=models.BooleanField(default=True, db_index=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='deleted',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='migrated',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AddField(
            model_name='preprint',
            name='article_doi',
            field= models.CharField(blank=True, max_length=128, null=True, validators=[osf.models.validators.validate_doi])
        ),
        migrations.AddField(
            model_name='preprint',
            name='last_logged',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, db_index=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AddField(
            model_name='preprint',
            name='tags',
            field=models.ManyToManyField(related_name='preprint_tagged', to='osf.Tag'),
        ),
        migrations.AddField(
            model_name='preprint',
            name='title',
            field=models.TextField(default='Untitled', validators=[osf.models.validators.validate_title]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='preprint',
            name='_contributors',
            field=models.ManyToManyField(related_name='preprints', through='osf.PreprintContributor', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='preprint',
            unique_together=set([]),
        ),
        migrations.AlterUniqueTogether(
            name='preprintcontributor',
            unique_together=set([('user', 'preprint')]),
        ),
        migrations.AlterOrderWithRespectTo(
            name='preprintcontributor',
            order_with_respect_to='preprint',
        ),
    ]
