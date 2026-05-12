from datetime import timedelta

import pytest
from mitol.common.utils import now_in_utc

from courses.factories import ProgramCertificateFactory, ProgramEnrollmentFactory
from courses.serializers.v3.programs import ProgramEnrollmentSerializer
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("with_certificate", [True, False])
def test_serialize_program_enrollment(user, with_certificate):
    """Test Program serialization"""
    enrollment = ProgramEnrollmentFactory.create(user=user)
    certificate = (
        ProgramCertificateFactory.create(program=enrollment.program, user=user)
        if with_certificate
        else None
    )

    data = ProgramEnrollmentSerializer(instance=enrollment).data

    assert_drf_json_equal(
        data,
        {
            "program": {
                "display_mode": None,
                "id": enrollment.program.id,
                "readable_id": enrollment.program.readable_id,
                "title": enrollment.program.title,
                "program_type": enrollment.program.program_type,
                "live": enrollment.program.live,
            },
            "certificate": {"uuid": certificate.uuid, "link": certificate.link}
            if with_certificate
            else None,
            "enrollment_mode": enrollment.enrollment_mode,
        },
    )


def test_serialize_program_enrollment_future_certificate_is_null(user):
    """
    When a ProgramCertificate has a future issue_date it should appear as null
    in the nested enrollment response, not raise a 404.
    """
    enrollment = ProgramEnrollmentFactory.create(user=user)
    ProgramCertificateFactory.create(
        program=enrollment.program,
        user=user,
        issue_date=now_in_utc() + timedelta(days=1),
    )

    data = ProgramEnrollmentSerializer(instance=enrollment).data

    assert data["certificate"] is None
