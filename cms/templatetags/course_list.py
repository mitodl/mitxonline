"""
Generates a <ul> block for a list of courses. Pass in the list of courses.
"""

from django import template

from cms.templatetags.feature_img_src import feature_img_src

register = template.Library()


def format_course_start_time(start_date):
    return f"{start_date.strftime('%B')} {start_date.day}, {start_date.year}"


@register.inclusion_tag("course_list_card.html", name="course_list")
def course_list(courses):
    cards = []

    for course in courses:
        page = course.course_page
        if not page or not page.live:
            continue

        start_descriptor = (
            f"Starts {format_course_start_time(course.first_unexpired_run.start_date)}"
            if course.first_unexpired_run and course.first_unexpired_run.start_date
            else "Start Anytime"
        )

        featured_image = feature_img_src(page.feature_image)

        cards.append(
            {
                "course": course,
                "page": page,
                "start_descriptor": start_descriptor,
                "featured_image": featured_image,
            }
        )

    return {"cards": cards}
