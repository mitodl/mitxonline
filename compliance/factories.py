"""Factories for the compliance app"""

from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from compliance.models import ExportComplianceDecision, ExportComplianceLog
from courses.factories import CourseRunFactory
from users.factories import UserFactory


class ExportComplianceLogFactory(DjangoModelFactory):
    """Factory for ExportComplianceLog"""

    user = SubFactory(UserFactory)
    courseware_object = SubFactory(CourseRunFactory)
    decision = FuzzyChoice(
        [
            ExportComplianceDecision.COMPLETED,
            ExportComplianceDecision.INVALID_REQUEST,
            ExportComplianceDecision.DECLINED,
        ]
    )
    reason_code = Faker("numerify", text="###")
    request_id = Faker("uuid4")
    encrypted_request = Faker("pystr", max_chars=30)
    encrypted_response = Faker("pystr", max_chars=30)

    class Meta:
        model = ExportComplianceLog
