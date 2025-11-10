# Generated migration to move programs from M2M to ContractProgramItem

from django.db import migrations


def migrate_programs_to_items(apps, schema_editor):
    """Migrate existing programs from M2M relationship to ContractProgramItem"""
    ContractPage = apps.get_model("b2b", "ContractPage")
    ContractProgramItem = apps.get_model("b2b", "ContractProgramItem")

    for contract in ContractPage.objects.all():
        # Get existing programs from the M2M relationship
        programs = contract.programs.all()

        # Create ContractProgramItem entries for each program
        for index, program in enumerate(programs):
            ContractProgramItem.objects.get_or_create(
                contract=contract, program=program, defaults={"sort_order": index}
            )


def reverse_migration(apps, schema_editor):
    """Reverse: copy data back from ContractProgramItem to M2M"""
    ContractPage = apps.get_model("b2b", "ContractPage")
    ContractProgramItem = apps.get_model("b2b", "ContractProgramItem")

    for contract in ContractPage.objects.all():
        # Get programs from ContractProgramItem
        items = ContractProgramItem.objects.filter(contract=contract).order_by(
            "sort_order"
        )

        # Add them back to the M2M relationship
        for item in items:
            contract.programs.add(item.program)


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0014_contractprogramitem"),
    ]

    operations = [
        migrations.RunPython(migrate_programs_to_items, reverse_migration),
    ]
