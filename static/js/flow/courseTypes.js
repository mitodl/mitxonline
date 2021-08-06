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
  courseware_url: ?string,
  courseware_id: string,
  run_tag: ?string,
  id: number
}

export type CourseRunDetail = BaseCourseRun & {
  course: CourseDetail
}

export type RunEnrollment = {
  run: CourseRunDetail
}
