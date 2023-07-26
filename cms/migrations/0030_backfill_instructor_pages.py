# Backfills InstructorPage with info that's currently trapped in CoursePage and
# ProgramPage. This will necessarily generate duplicates - 

from django.db import migrations


def get_instructor_data_from_pages(apps, schema_editor):
    InstructorPage = apps.get_model('cms', 'InstructorPage')
    InstructorPageLink = apps.get_model('cms', 'InstructorPageLink')
    CoursePage = apps.get_model('cms', 'CoursePage')
    ProgramPage = apps.get_model('cms', 'ProgramPage')
    Image = apps.get_model('wagtailimages', 'Image')

    for coursepage in CoursePage.objects.all():
        ibvalues = [ block.get_prep_value()['value'] for block in coursepage.faculty_members ]

        for block in ibvalues:
            existingcount = InstructorPage.objects.filter(instructor_name=block['name']).count() > 0

            if existingcount > 0:
                block['name'] += f" {(existingcount + 1)}"
            
            try:
                featured_image = Image.objects.get(pk=block['image']) 
            except Exception:
                featured_image = None
            
            new_instructor = InstructorPage(
                instructor_name=block['name'],
                feature_image=featured_image,
                instructor_bio_short=block['description']
            ).save()

            InstructorPageLink(
                page=coursepage,
                linked_instructor_page=new_instructor
            ).save()


def undo_instructor_data(apps, schema_editor):
    """just ignore for now"""
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0029_add_linked_instructors_to_product_pages'),
    ]

    operations = [
        migrations.RunPython(get_instructor_data_from_pages, undo_instructor_data)
    ]
