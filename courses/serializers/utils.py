"""Utility functions for serializers"""

from courses.models import CoursesTopic


def get_topics_from_page(page_instance) -> list[dict]:
    """
    Extract topics from a page instance, including parent topics.

    This function handles the common logic for extracting topics from course/program pages,
    including fetching parent topics to avoid duplication across serializers.

    Args:
        page_instance: The page instance that has a topics relationship

    Returns:
        List of topic dictionaries with 'name' key, sorted alphabetically
    """
    if not page_instance:
        return []

    # Get direct topics from the page
    direct_topics = page_instance.topics.all()

    # Get parent topics for the direct topics
    parent_topics = CoursesTopic.objects.filter(
        child_topics__in=direct_topics
    ).distinct()

    # Create list of topic names, starting with direct topics
    all_topics = sorted(
        [{"name": topic.name} for topic in direct_topics],
        key=lambda topic: topic["name"],
    )

    # Add parent topics
    for parent_topic in parent_topics:
        all_topics.append({"name": parent_topic.name})

    return all_topics


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
