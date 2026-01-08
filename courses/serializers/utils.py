"""Utility functions for serializers"""


def get_topics_from_page(page_instance) -> list[dict]:
    """
    Extract topics from a page instance, including parent topics.

    This function handles the common logic for extracting topics from course/program pages,
    including fetching parent topics to avoid duplication across serializers.

    Args:
        page_instance: The page instance that has a topics relationship

    Returns:
        List of topic dictionaries with 'name' key, with direct topics sorted first,
        followed by parent topics sorted separately
    """
    if not page_instance:
        return []

    # Get direct topics from the page (this should be prefetched)
    direct_topics = page_instance.topics.all()

    # Collect direct topics names and parent topic names separately
    direct_topic_names = set()
    parent_topic_names = set()

    # First pass: collect all direct topic names
    for topic in direct_topics:
        direct_topic_names.add(topic.name)

    # Second pass: collect parent topics that are not already in direct topics
    for topic in direct_topics:
        if topic.parent and topic.parent.name not in direct_topic_names:
            parent_topic_names.add(topic.parent.name)

    # Sort direct topics first, then parent topics
    sorted_direct = sorted(
        [{"name": name} for name in direct_topic_names], key=lambda topic: topic["name"]
    )
    sorted_parents = [{"name": name} for name in sorted(parent_topic_names)])

    # Return direct topics first, then parent topics
    return sorted_direct + sorted_parents


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
