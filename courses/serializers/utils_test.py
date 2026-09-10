"""Unit tests for courses.serializers.utils module"""

from unittest.mock import Mock

import pytest

from cms.factories import CoursePageFactory
from courses.factories import CoursesTopicFactory
from courses.serializers.utils import get_topics_from_page

pytestmark = [pytest.mark.django_db]


class TestGetTopicsFromPage:
    """Test cases for get_topics_from_page function"""

    def test_get_topics_from_page_with_none_page_instance(self):
        """Test that None page instance returns empty list"""
        result = get_topics_from_page(None)
        assert result == []

    def test_get_topics_from_page_with_empty_topics(self):
        """Test page instance with no topics returns empty list"""
        mock_page = Mock()
        mock_page.topics.all.return_value = []

        result = get_topics_from_page(mock_page)
        assert result == []

    def test_get_topics_from_page_with_direct_topics_only(self):
        """Test page with direct topics but no parent topics"""
        # Create topics without parent topics
        topic1 = CoursesTopicFactory.create(name="Mathematics")
        topic2 = CoursesTopicFactory.create(name="Computer Science")
        topic3 = CoursesTopicFactory.create(name="Physics")

        mock_page = Mock()
        mock_page.topics.all.return_value = [topic1, topic2, topic3]

        result = get_topics_from_page(mock_page)

        # Should be sorted alphabetically
        expected = [
            {"name": "Computer Science"},
            {"name": "Mathematics"},
            {"name": "Physics"},
        ]
        assert result == expected

    def test_get_topics_from_page_with_parent_topics(self):
        """Test page with topics that have parent topics"""
        # Create parent topics
        parent_topic1 = CoursesTopicFactory.create(name="Science", parent=None)
        parent_topic2 = CoursesTopicFactory.create(name="Technology", parent=None)

        # Create child topics
        child_topic1 = CoursesTopicFactory.create(name="Physics", parent=parent_topic1)
        child_topic2 = CoursesTopicFactory.create(
            name="Chemistry", parent=parent_topic1
        )
        child_topic3 = CoursesTopicFactory.create(
            name="Programming", parent=parent_topic2
        )

        mock_page = Mock()
        mock_page.topics.all.return_value = [child_topic1, child_topic2, child_topic3]

        result = get_topics_from_page(mock_page)

        # Should include both direct topics (sorted) and parent topics
        expected_direct_topics = [
            {"name": "Chemistry"},
            {"name": "Physics"},
            {"name": "Programming"},
        ]

        # Parent topics should be appended after direct topics
        # Note: The order of parent topics may vary since they're added in a loop
        assert len(result) == 5  # 3 direct + 2 parent topics

        # Check that all direct topics are present at the beginning (sorted)
        for i, expected_topic in enumerate(expected_direct_topics):
            assert result[i] == expected_topic

        # Check that parent topics are included
        parent_topic_names = {result[i]["name"] for i in range(3, 5)}
        assert parent_topic_names == {"Science", "Technology"}

    def test_get_topics_from_page_with_mixed_parent_and_orphan_topics(self):
        """Test page with mix of topics that have parents and topics without parents"""
        # Create parent topic
        parent_topic = CoursesTopicFactory.create(name="Science", parent=None)

        # Create child topic
        child_topic = CoursesTopicFactory.create(name="Physics", parent=parent_topic)

        # Create orphan topics (no parent)
        orphan_topic1 = CoursesTopicFactory.create(name="Art", parent=None)
        orphan_topic2 = CoursesTopicFactory.create(name="Literature", parent=None)

        mock_page = Mock()
        mock_page.topics.all.return_value = [child_topic, orphan_topic1, orphan_topic2]

        result = get_topics_from_page(mock_page)

        # Should have 3 direct topics + 1 parent topic
        assert len(result) == 4

        # Check direct topics are sorted alphabetically
        expected_direct_topics = [
            {"name": "Art"},
            {"name": "Literature"},
            {"name": "Physics"},
        ]

        for i, expected_topic in enumerate(expected_direct_topics):
            assert result[i] == expected_topic

        # Check parent topic is included
        assert result[3] == {"name": "Science"}

    def test_get_topics_from_page_with_multiple_parent_topics(self):
        """Test page with topics from different parent categories"""
        # Create multiple parent topics
        science_parent = CoursesTopicFactory.create(name="Science", parent=None)
        tech_parent = CoursesTopicFactory.create(name="Technology", parent=None)
        arts_parent = CoursesTopicFactory.create(name="Arts", parent=None)

        # Create child topics under different parents
        physics_topic = CoursesTopicFactory.create(
            name="Physics", parent=science_parent
        )
        programming_topic = CoursesTopicFactory.create(
            name="Programming", parent=tech_parent
        )
        music_topic = CoursesTopicFactory.create(name="Music", parent=arts_parent)

        mock_page = Mock()
        mock_page.topics.all.return_value = [
            physics_topic,
            programming_topic,
            music_topic,
        ]

        result = get_topics_from_page(mock_page)

        # Should have 3 direct topics + 3 parent topics
        assert len(result) == 6

        # Check direct topics are sorted alphabetically
        expected_direct_topics = [
            {"name": "Music"},
            {"name": "Physics"},
            {"name": "Programming"},
        ]

        for i, expected_topic in enumerate(expected_direct_topics):
            assert result[i] == expected_topic

        # Check that all parent topics are included
        parent_topic_names = {result[i]["name"] for i in range(3, 6)}
        assert parent_topic_names == {"Arts", "Science", "Technology"}

    def test_get_topics_from_page_single_topic_with_parent(self):
        """Test edge case with single topic that has a parent"""
        # Create parent topic
        parent_topic = CoursesTopicFactory.create(name="Science", parent=None)

        # Create single child topic
        child_topic = CoursesTopicFactory.create(name="Physics", parent=parent_topic)

        mock_page = Mock()
        mock_page.topics.all.return_value = [child_topic]

        result = get_topics_from_page(mock_page)

        # Should have 1 direct topic + 1 parent topic
        assert len(result) == 2
        assert result[0] == {"name": "Physics"}
        assert result[1] == {"name": "Science"}

    def test_get_topics_from_page_with_course_page_object(self):
        """Test integration with actual CoursesTopic model and database queries"""
        # Create real topics with parent-child relationships
        parent_topic = CoursesTopicFactory.create(name="Computer Science")
        child_topic1 = CoursesTopicFactory.create(
            name="Machine Learning", parent=parent_topic
        )
        child_topic2 = CoursesTopicFactory.create(
            name="Data Science", parent=parent_topic
        )
        orphan_topic = CoursesTopicFactory.create(name="Mathematics")

        # Create a real CoursePage and assign topics to it
        course_page = CoursePageFactory.create()
        course_page.topics.set([child_topic1, child_topic2, orphan_topic])

        # This will actually test the CoursesTopic.objects.filter logic
        result = get_topics_from_page(course_page)

        # Should have 3 direct topics + 1 parent topic
        assert len(result) == 4

        # Verify direct topics are sorted
        expected_direct_topics = [
            {"name": "Data Science"},
            {"name": "Machine Learning"},
            {"name": "Mathematics"},
        ]

        for i, expected_topic in enumerate(expected_direct_topics):
            assert result[i] == expected_topic

        # Verify parent topic is included (found via database query)
        assert result[3] == {"name": "Computer Science"}

    def test_get_topics_from_page_preserves_sorting_with_unicode_characters(self):
        """Test that sorting works correctly with unicode characters"""
        # Create topics with unicode characters
        topic1 = CoursesTopicFactory.create(name="Ångström Physics")
        topic2 = CoursesTopicFactory.create(name="Ácoustics")
        topic3 = CoursesTopicFactory.create(name="Basic Math")

        mock_page = Mock()
        mock_page.topics.all.return_value = [topic1, topic2, topic3]

        result = get_topics_from_page(mock_page)

        # Python's default sorting treats accented characters after non-accented ones
        # This reflects the actual behavior of the sorted() function in Python
        expected = [
            {"name": "Basic Math"},
            {"name": "Ácoustics"},
            {"name": "Ångström Physics"},
        ]
        assert result == expected

    def test_get_topics_from_page_does_not_dedupe_parent_against_direct(self):
        """
        A parent whose name matches a direct topic must appear twice.

        This is the contract #3169 broke (it deduplicated parents against direct
        topics), which is why #3213 reverted it. Pinning it here so the shape of
        the ``topics`` array cannot be "tidied up" by accident.
        """
        science = CoursesTopicFactory.create(name="Science", parent=None)
        # A direct topic with the same name as the parent, under a different
        # parent, so unique_together ("name", "parent") still holds.
        other = CoursesTopicFactory.create(name="Other", parent=None)
        science_direct = CoursesTopicFactory.create(name="Science", parent=other)
        physics = CoursesTopicFactory.create(name="Physics", parent=science)

        mock_page = Mock()
        mock_page.topics.all.return_value = [physics, science_direct]

        result = get_topics_from_page(mock_page)

        # Direct topics sorted by name, then the distinct parents appended.
        assert result == [
            {"name": "Physics"},
            {"name": "Science"},
            {"name": "Other"},
            {"name": "Science"},
        ]

    def test_get_topics_from_page_orders_parents_by_model_ordering(self):
        """
        Parents come back in ``CoursesTopic.Meta.ordering`` order.

        That is ``["parent__name", "name"]``, and Postgres sorts NULLs last for
        ASC - so parents that themselves have a parent sort before top-level
        ones, and the derived-in-Python ordering has to match.
        """
        top_b = CoursesTopicFactory.create(name="B-top", parent=None)
        top_a = CoursesTopicFactory.create(name="A-top", parent=None)
        # mid_* have a non-null parent, so they sort ahead of the top-level ones.
        mid = CoursesTopicFactory.create(name="Zebra", parent=top_a)

        leaf_of_top_b = CoursesTopicFactory.create(name="leaf1", parent=top_b)
        leaf_of_top_a = CoursesTopicFactory.create(name="leaf2", parent=top_a)
        leaf_of_mid = CoursesTopicFactory.create(name="leaf3", parent=mid)

        mock_page = Mock()
        mock_page.topics.all.return_value = [
            leaf_of_top_b,
            leaf_of_top_a,
            leaf_of_mid,
        ]

        result = get_topics_from_page(mock_page)
        parent_names = [entry["name"] for entry in result[3:]]

        # "Zebra" has parent "A-top" (non-null) so it leads; "A-top" and
        # "B-top" have no parent, so they sort last, by name.
        assert parent_names == ["Zebra", "A-top", "B-top"]
