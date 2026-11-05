from django.contrib.auth import get_user_model

from courses.models import CourseRun, CourseRunCertificate, Program, ProgramCertificate

User = get_user_model()


def maybe_serialize_program_cert(program: Program, user: "User"):
    cert = ProgramCertificate.objects.filter(program=program, user=user).first()
    return (
        {
            "uuid": str(cert.uuid),
            "link": cert.link,
        }
        if cert
        else None
    )


def maybe_serialize_course_cert(run: CourseRun, user: "User"):
    cert = CourseRunCertificate.objects.filter(course_run=run, user=user).first()
    return (
        {
            "uuid": str(cert.uuid),
            "link": cert.link,
        }
        if cert
        else None
    )
