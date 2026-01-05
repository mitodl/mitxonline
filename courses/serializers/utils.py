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

    # Get direct topics from the page (this should be prefetched)
    direct_topics = page_instance.topics.all()

    # Use a set to track all topics (direct + parent) and avoid duplicates
    all_topic_names = set()
    
    # Add direct topics and their parents
    for topic in direct_topics:
        all_topic_names.add(topic.name)
        # Add parent topic name if it exists (parent should be prefetched)
        if topic.parent:
            all_topic_names.add(topic.parent.name)

    # Return sorted list of topic dictionaries
    return sorted(
        [{"name": name} for name in all_topic_names],
        key=lambda topic: topic["name"],
    )


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
