import casual from "casual-browserify"
import {
  BaseCourseRun,
  CourseDetail,
  CourseRunDetail,
  RunEnrollment
} from "../types/course"
import { incrementer } from "./util"

const genCourseRunId = incrementer()
const genEnrollmentId = incrementer()
const genCoursewareId = incrementer()
const genRunTagNumber = incrementer()

export const makeCourseRun = (): BaseCourseRun => ({
  title:            casual.text,
  start_date:       casual.moment.add(2, "M").format(),
  end_date:         casual.moment.add(4, "M").format(),
  enrollment_start: casual.moment.add(-1, "M").format(),
  enrollment_end:   casual.moment.add(3, "M").format(),
  courseware_url:   casual.url,
  courseware_id:    casual.word.concat(genCoursewareId.next().value),
  run_tag:          casual.word.concat(genRunTagNumber.next().value),
  id:               genCourseRunId.next().value,
  course_number:    casual.word
})
const genCourseId = incrementer()

const makeCourseDetail = (): CourseDetail => ({
  id:                genCourseId.next().value,
  title:             casual.text,
  description:       casual.text,
  readable_id:       casual.word,
  feature_image_src: casual.url
})

export const makeCourseRunDetail = (): CourseRunDetail => {
  return { ...makeCourseRun(), course: makeCourseDetail() }
}

export const makeCourseRunEnrollment = (): RunEnrollment => ({
  id:                      genEnrollmentId.next().value,
  run:                     makeCourseRunDetail(),
  edx_emails_subscription: true
})
