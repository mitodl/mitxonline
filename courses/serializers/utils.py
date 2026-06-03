"""Utility functions for serializers"""


def get_unique_topics_from_courses(courses) -> list[dict]:
    """
    Extract unique topics from a collection of courses.

    This function handles extracting topics from multiple courses and returns
    a deduplicated, sorted list.

    Args:
        courses: Iterable of course objects that have page.topics relationships

    Returns:
        List of unique topic dictionaries with 'name' key, sorted alphabetically
    """
    topics = set()

    for course in courses:
        if hasattr(course, "page") and course.page:
            topics.update(topic.name for topic in course.page.topics.all())

    return [{"name": topic} for topic in sorted(topics)]
