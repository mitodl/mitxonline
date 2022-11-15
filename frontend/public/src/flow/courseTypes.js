import type { Product } from "./ecommerceTypes"
import type { Page } from "./cmsTypes"

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
