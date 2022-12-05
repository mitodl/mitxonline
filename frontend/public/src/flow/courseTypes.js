import type { Product } from "./ecommerceTypes"
import type { Page } from "./cmsTypes"
import type { LearnerRecordUser } from "./authTypes"

export type CourseDetail = {
  id: number,
  title: string,
  readable_id: string,
  feature_image_src: ?string
}

export type BaseCourseRun = {
  title: string,
  start_date: ?string,
  end_date: ?string,
  enrollment_start: ?string,
  enrollment_end: ?string,
  upgrade_deadline: ?string,
  is_upgradable: boolean,
  courseware_url: ?string,
  courseware_id: string,
  run_tag: ?string,
  products: Array<Product>,
  id: number,
  page: ?Page,
  course_number: ?string
}

export type EnrollmentFlaggedCourseRun = BaseCourseRun & {
  expiration_date: ?string,
  is_enrolled: boolean
}

export type CourseRunDetail = BaseCourseRun & {
  course: CourseDetail
}

export type Certificate = {
  link: string,
  uuid: string
}

export type CourseRunGrade = {
  grade:         number,
  letter_grade:  string,
  passed:        boolean,
  set_by_admin:  boolean,
  grade_percent: number,
}

export type RunEnrollment = {
  run: CourseRunDetail,
  id: number,
  edx_emails_subscription: ?string,
  enrollment_mode: string,
  certificate: ?Certificate,
  grades: Array<CourseRunGrade>,
}

export type CourseDetailWithRuns = CourseDetail & {
  courseruns: Array<BaseCourseRun>
}

export type ProgramEnrollments = {
  electives: Array<number>,
  required: Array<number>,
}

export type Program = {
  id: number,
  title: string,
  readable_id: string,
  courses: Array<CourseDetailWithRuns>,
  requirements: ?ProgramEnrollments,
}

export type ProgramEnrollment = {
  program: Program,
  enrollments: Array<RunEnrollment>,
  certificate: ?Certificate
}

export type PartnerSchool = {
  id: number,
  name: string,
  email: string
}

export type RequirementNode = {
  node_type: string,
  operator: ?string,
  operator_value: ?number,
  program: number,
  course: ?number,
  title: ?string,
}

export type ProgramRequirement = {
  id: number,
  data: RequirementNode,
  children: Array<ProgramRequirement>,
}

export type LearnerRecordGrade = {
  grade: number,
  letter_grade: string,
  passed: boolean,
  set_by_admin: boolean,
  grade_percent: number
}

export type LearnerRecordCertificate = {
  uuid: string,
  link: string
}

export type LearnerRecordCourse = {
  title: string,
  id: number,
  readable_id: string,
  reqtype: ?string,
  grade: ?LearnerRecordGrade,
  certificate: ?LearnerRecordCertificate
}

export type LearnerRecordProgram = {
  title: string,
  readable_id: string,
  courses: Array<LearnerRecordCourse>,
  requirements: Array<ProgramRequirement>,
}

export type LearnerRecordShare = {
  share_uuid: string,
  created_on: string,
  updated_on: string,
  is_active: boolean,
  user: number,
  program: number,
  partner_school: ?number
}

export type LearnerRecord = {
  user: LearnerRecordUser,
  program: LearnerRecordProgram,
  sharing: Array<LearnerRecordShare>,
  partner_schools: Array<PartnerSchool>,
}
