"""
Generates a <ul> block for a list of courses. Pass in the list of courses.
"""

import re

from django import template

from cms.templatetags.feature_img_src import feature_img_src

register = template.Library()


def format_course_start_time(start_date):
    hour = start_date.hour
    minute = start_date.minute
    timespec = ""

    if (hour == 23 and minute == 59) or (hour == 0 and minute == 0):
        timespec = "midnight"
    else:
        timespec = re.sub(r"^0", "", start_date.strftime("%I:%M %p"))

    return (
        f"{start_date.strftime('%b')} {start_date.day}, {start_date.year}, {timespec}"
    )


@register.inclusion_tag("course_list_card.html", name="course_list")
def course_list(courses):
    cards = []

    for course in courses:
        start_descriptor = (
            f"Starts {format_course_start_time(course.first_unexpired_run.start_date)}"
            if course.first_unexpired_run and course.first_unexpired_run.start_date
            else "Start Anytime"
        )
        featured_image = feature_img_src(course.page.feature_image)

        cards.append(
            {
                "course": course,
                "start_descriptor": start_descriptor,
                "featured_image": featured_image,
            }
        )

    return {"cards": cards}
