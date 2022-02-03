/* eslint camelcase: "off" */
export type CourseDetail = {
  id: number
  title: string
  description: string
  readable_id: string
  feature_image_src: string | null | undefined
}

export type BaseCourseRun = {
  title: string
  start_date: string | null | undefined
  end_date: string | null | undefined
  enrollment_start: string | null | undefined
  enrollment_end: string | null | undefined
  courseware_url: string | null | undefined
  courseware_id: string
  run_tag: string | null | undefined
  id: number
  course_number: string
}

export type EnrollmentFlaggedCourseRun = BaseCourseRun & {
  expiration_date: string | null | undefined
  is_enrolled: boolean
}

export type CourseRunDetail = BaseCourseRun & {
  course: CourseDetail
}

export type RunEnrollment = {
  run: CourseRunDetail
  id: number
  edx_emails_subscription: boolean
}
