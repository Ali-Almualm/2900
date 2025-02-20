# Generated by Django 5.1.5 on 2025-02-13 14:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_alter_booking_options_alter_booking_booking_type_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='booking',
            options={},
        ),
        migrations.AlterField(
            model_name='booking',
            name='booking_type',
            field=models.CharField(choices=[('pool', 'Pool'), ('switch', 'Nintendo Switch'), ('table_tennis', 'Table Tennis')], max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name='booking',
            unique_together={('start_time', 'booking_type')},
        ),
        migrations.AlterModelTable(
            name='booking',
            table='bookings',
        ),
    ]
