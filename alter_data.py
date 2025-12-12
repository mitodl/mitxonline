#
# from django.contrib.auth import get_user_model
#
# User = get_user_model()
#
# user = User.objects.filter(email="nguyenhienthudong09112003@gmail.com").first()
# from openedx.api import *
#
# repair_faulty_edx_user(user)
#
# #### repair enrollments
# from openedx.api import *
# retry_failed_edx_enrollments()
#
# sync_enrollments_with_edx(user)
# #### Syncing grades
# from courses.models import *
# course_run = CourseRun.objects.filter(courseware_id="course-v1:MITxT+14.310x+2T2025").first()
#
#
# ./manage.py manage_certificates --create --run=course-v1:MITxT+14.310x+2T2025 --user=rutyolandakbl@gmail.com
#
# ### Find duplicate accounts
# from django.contrib.auth import get_user_model
# User = get_user_model()
# from django.db.models import Count
# User.objects.values("global_id").annotate(count_id=Count("global_id")).filter(count_id__gt=1).values_list('global_id', flat=True)
# User.objects.filter(global_id="")
# # Deleted users
# albert@albertquigley.coach
# m.denys@students.hertie-school.org
# madhavgoenka4@gmail.com
# info@nicolegaillard.nl
# frances.buckingham@gmail.com
#
#
#
#
# from ecommerce.models import *
# order = Order.objects.filter(purchaser__email="kotchiamonchy@yahoo.fr").first()
# order.status = OrderStatus.REFUNDED
# order.save()
#
#
#
#
# # Email changed from ramospuentejulia@gmail.com to retired_email_69d23c7db75b94fb212b270257e27ee46d0decba@retired.mitxonline.mit.edu and password is not useable now
# # For  user: 'juls29rp' SocialAuth rows deleted
# # User: 'juls29rp' is retired from MITx Online
#
#
# #### Discounts
#
# ./manage.py generate
#
# ./manage.py generate_discount_code  --count 12 --payment-type customer-support  --prefix B2B_DEDP_Scholarship_ --expires 2027-12-31 --one-time --amount 100 --discount-type percent-off
#
# ./manage.py generate_discount_code  --count 2 --payment-type customer-support  --prefix B2B_ENSEA_3T2025 --expires 2026-08-15 --one-time --amount 100 --discount-type percent-off
#
#
#
# from courses.models import *
# grade = CourseRunGrade.objects.filter(course_run__courseware_id="course-v1:MITxT+14.310x+2T2025").first()
# grade.updated_on
#
# grades = CourseRunGrade.objects.filter(course_run__courseware_id="course-v1:MITxT+14.310x+2T2025").order_by("updated_on")
#
# for grade in grades:
#     print(grade.updated_on)
#     count+=1
#     if count>20: break
#
# ########## defer enrollment
# ./manage.py defer_enrollment --user in.abhayverma@gmail.com --from-run course-v1:MITxT+14.003x+2T2025 --to-run course-v1:MITxT+14.003x+3T2025
#
#
# from django.contrib.auth import get_user_model
# User = get_user_model()
# user = User.objects.filter(email="in.abhayverma@gmail.com").first()
# from courses.api import *
# defer_enrollment(user, "course-v1:MITxT+14.003x+2T2025", "course-v1:MITxT+14.003x+3T2025", force=True)
#
# from_courseware_id = "course-v1:MITxT+14.003x+2T2025"
# from_enrollment = CourseRunEnrollment.all_objects.get(user=user, run__courseware_id=from_courseware_id)
#
#
# #### trying out deferal for my user
# from django.contrib.auth import get_user_model
# User = get_user_model()
# user = User.objects.filter(email="anna.gavrilman@gmail.com").first()
# from courses.api import *
# defer_enrollment(user, "course-v1:MITxT+JPAL102x+2T2026", "course-v1:MITxT+JPAL102x+3T2024", force=True)
#
# #### enroll in edx
# run = CourseRun.objects.filter(courseware_id="course-v1:MITxT+14.003x+3T2025").first()
# enroll_in_edx_course_runs(user, [run],mode=EDX_ENROLLMENT_VERIFIED_MODE)
#
#
# ##### Creating an Organization and contract
# ./manage.py b2b_contract create --create UniversityX "UniversityX Contract" sso --description "Test uncapped SSO contract" --org-key uniX
#
# ./manage.py b2b_contract courseware 53 "course-v1:MITxT+0.001x"
#
# ./manage.py b2b_courseware add --no-create-runs 53  "course-v1:MITxT+0.001x"
#
#
# from users.models import User
# from b2b.models import OrganizationPage, ContractPage
#
# mit = OrganizationPage.objects.get(id=702)
# contract = ContractPage.objects.get(id=708)
# from django.contrib.auth import get_user_model
#
# User = get_user_model()
# u = User.objects.filter(email__endswith='duth.gr')
#
# for learner in u:
#     mit.add_user_contracts(learner)
#
#
# mit = OrganizationPage.objects.get(id=703)
# # contract = ContractPage.objects.get(id=709)
# from django.contrib.auth import get_user_model
#
# User = get_user_model()
# u = User.objects.filter(email__endswith='athenscollege.edu.gr')
#
# for learner in u:
#     mit.add_user_contracts(learner)
#
#
# ./manage.py unenroll_enrollment --user=thefatcat1986@gmail.com --run=course-v1:MITxT+8.01.1x+3T2025
#
#
# from openedx.api import *
# from openedx.constants import *
# courseware_id="course-v1:MITxT+14.100x+2T2024"
# edx_client = get_edx_api_service_client()
# enrollment = edx_client.enrollments.create_student_enrollment(courseware_id, mode=EDX_ENROLLMENT_VERIFIED_MODE, username="annagav", force_enrollment=True)
