// @flow
import casual from "casual-browserify"

import { incrementer } from "./util"

import type {
  CourseRun,
  CourseRunDetail,
  CourseRunEnrollment,
  CourseDetail,
  CourseDetailWithRuns,
  ProgramEnrollment,
  Program
} from "../flow/courseTypes"

const genCourseRunId = incrementer()
const genEnrollmentId = incrementer()
const genCoursewareId = incrementer()
const genRunTagNumber = incrementer()
const genProductId = incrementer()
const genProgramId = incrementer()

export const makeCourseRun = (): CourseRun => ({
  title:            casual.text,
  start_date:       casual.moment.add(2, "M").format(),
  end_date:         casual.moment.add(4, "M").format(),
  enrollment_start: casual.moment.add(-1, "M").format(),
  enrollment_end:   casual.moment.add(3, "M").format(),
  upgrade_deadline: casual.moment.add(4, "M").format(),
  courseware_url:   casual.url,
  courseware_id:    casual.word.concat(genCoursewareId.next().value),
  run_tag:          casual.word.concat(genRunTagNumber.next().value),
  // $FlowFixMe
  id:               genCourseRunId.next().value,
  course_number:    casual.word,
  products:         []
})

export const makeCourseRunWithProduct = (): CourseRun => ({
  title:            casual.text,
  start_date:       casual.moment.add(2, "M").format(),
  end_date:         casual.moment.add(4, "M").format(),
  enrollment_start: casual.moment.add(-1, "M").format(),
  enrollment_end:   casual.moment.add(3, "M").format(),
  upgrade_deadline: casual.moment.add(4, "M").format(),
  courseware_url:   casual.url,
  courseware_id:    casual.word.concat(genCoursewareId.next().value),
  run_tag:          casual.word.concat(genRunTagNumber.next().value),
  // $FlowFixMe
  id:               genCourseRunId.next().value,
  course_number:    casual.word,
  page:             { financial_assistance_form_url: casual.url },
  is_upgradable:    true,
  products:         [
    {
      description:            casual.text,
      id:                     genProductId.next().value,
      is_active:              true,
      price:                  casual.integer(1, 200),
      product_flexible_price: {
        amount:               null,
        automatic:            false,
        discount_type:        null,
        redemption_type:      null,
        max_redemptions:      null,
        discount_code:        "",
        for_flexible_pricing: false
      }
    }
  ]
})

const genCourseId = incrementer()
const makeCourseDetail = (): CourseDetail => ({
  // $FlowFixMe
  id:                genCourseId.next().value,
  title:             casual.text,
  description:       casual.text,
  readable_id:       casual.word,
  feature_image_src: casual.url
})

export const makeCourseDetailWithRuns = (): CourseDetailWithRuns => {
  return {
    ...makeCourseRun(),
    courseruns: [makeCourseRun()]
  }
}

export const makeCourseRunDetail = (): CourseRunDetail => {
  return {
    ...makeCourseRun(),
    course: makeCourseDetail()
  }
}

export const makeCourseRunDetailWithProduct = (): CourseRunDetail => {
  return {
    ...makeCourseRunWithProduct(),
    course: makeCourseDetail()
  }
}

const genEnrollmentMode = () => {
  const modes = ["audit", "verified"]

  return modes[Math.random() * modes.length]
}

export const makeCourseRunEnrollment = (): CourseRunEnrollment => ({
  // $FlowFixMe
  id:                      genEnrollmentId.next().value,
  run:                     makeCourseRunDetail(),
  edx_emails_subscription: true,
  enrollment_mode:         genEnrollmentMode()
})

export const makeCourseRunEnrollmentWithProduct = (): CourseRunEnrollment => ({
  // $FlowFixMe
  id:                      genEnrollmentId.next().value,
  run:                     makeCourseRunDetailWithProduct(),
  edx_emails_subscription: true,
  enrollment_mode:         genEnrollmentMode()
})

export const makeProgram = (): Program => ({
  id:          genProgramId.next().value,
  title:       casual.text,
  readable_id: casual.word,
  courses:     [makeCourseDetailWithRuns()]
})

export const makeProgramEnrollment = (): ProgramEnrollment => ({
  program:     makeProgram(),
  enrollments: makeCourseRunEnrollment()
})
