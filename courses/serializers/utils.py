"""Utility functions for serializers"""


def _parent_topic_sort_key(topic):
    """
    Sort key reproducing ``CoursesTopic.Meta.ordering == ["parent__name", "name"]``.

    Postgres sorts NULLs last for ASC, and ``False < True``, so the leading
    ``topic.parent is None`` term puts parentless topics at the end just as the
    database does.
    """
    return (topic.parent is None, topic.parent.name if topic.parent else "", topic.name)


def has_live_certificate_page(instance) -> bool:
    """
    Return whether a course/program has a live certificate page, preferring
    the queryset-annotated `has_live_certificate_page` field (avoids N+1)
    and falling back to the `certificate_page` property when unannotated.
    """
    return (
        instance.has_live_certificate_page
        if hasattr(instance, "has_live_certificate_page")
        else instance.certificate_page is not None
    )


def get_topics_from_page(page_instance) -> list[dict]:
    """
    Extract topics from a page instance, including parent topics.

    This function handles the common logic for extracting topics from course/program pages,
    including fetching parent topics to avoid duplication across serializers.

    The parent topics are derived in Python from the direct topics' ``parent``
    relation rather than queried, so a caller that prefetches the topics (see
    ``CourseViewSet.get_queryset``, which selects ``parent`` and
    ``parent__parent``) pays no query per page. The output is unchanged: direct
    topics sorted by name, then the distinct parents in the model's own
    ordering, and parents are *not* deduplicated against the direct topics.

    Args:
        page_instance: The page instance that has a topics relationship

    Returns:
        List of topic dictionaries with 'name' key, sorted alphabetically
    """
    if not page_instance:
        return []

    # Get direct topics from the page
    direct_topics = page_instance.topics.all()

    # Get parent topics for the direct topics, deduplicated by pk the way the
    # equivalent .distinct() query was.
    parents_by_pk = {
        topic.parent.pk: topic.parent for topic in direct_topics if topic.parent
    }

    # Create list of topic names, starting with direct topics
    all_topics = sorted(
        [{"name": topic.name} for topic in direct_topics],
        key=lambda topic: topic["name"],
    )

    # Add parent topics
    for parent_topic in sorted(parents_by_pk.values(), key=_parent_topic_sort_key):
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
        course_page = course.course_page
        if course_page:
            topics.update(topic.name for topic in course_page.topics.all())

    return [{"name": topic} for topic in sorted(topics)]
