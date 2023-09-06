"""
Generates a list of <li> elements for a given set of courses. Pass in the list
of courses and it should spit out a bunch of <li> tags. 
"""

from django import template
from django.utils.safestring import mark_safe

from cms.templatetags.feature_img_src import feature_img_src

register = template.Library()


@register.simple_tag(name="course_list")
def course_list(courses):
    retstr = ""

    for course in courses:
        start_descriptor = (
            course.first_unexpired_run.start_date
            if course.first_unexpired_run.start_date
            else "Start Anytime"
        )
        featured_image = feature_img_src(course.page.feature_image)

        retstr += f"""
                  <li onClick="javascript:window.open('{course.page.url}');"> 
                    <div class="program-course-card">
                      <img src="{featured_image}" alt="">
                      <div class="program-course-card-info">
                        <h4 class="startdate">
                          {start_descriptor}
                        </h4>
                        <h3 class="title">{course.title}</h3>
                      </div>
                    </div>
                  </li>
"""

    return mark_safe(retstr)
