from django.db import migrations

# 0112 removed `b2b_contract` from Django's state but left the column, because
# the release before it still selected it while pods rolled.
DROP = """
ALTER TABLE courses_courserun DROP COLUMN b2b_contract_id;
"""

# The column as 0112 left it, without the FK constraint; reversing 0112 adds
# the constraint back and refills the column.
RESTORE = """
ALTER TABLE courses_courserun ADD COLUMN b2b_contract_id integer NULL;
CREATE INDEX courses_courserun_b2b_contract_id_dc76c49b
    ON courses_courserun (b2b_contract_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0113_certificate_page_revision_not_nullable"),
    ]

    operations = [
        migrations.RunSQL(DROP, reverse_sql=RESTORE),
    ]
