// @flow
import casual from "casual-browserify"

import { incrementer } from "./util"

import type { LearnerRecordUser } from "../flow/authTypes"

import type {
  Certificate,
  CourseRun,
  CourseRunDetail,
  CourseRunEnrollment,
  CourseDetail,
  CourseDetailWithRuns,
  ProgramEnrollment,
  Program,
  PartnerSchool,
  LearnerRecord,
  LearnerRecordCertificate,
  ProgramRequirement,
  LearnerRecordGrade,
  LearnerRecordCourse,
  LearnerRecordProgram,
  LearnerRecordShare
} from "../flow/courseTypes"

const genCourseRunId = incrementer()
const genEnrollmentId = incrementer()
const genCoursewareId = incrementer()
const genRunTagNumber = incrementer()
const genProductId = incrementer()
const genProgramId = incrementer()
const genPartnerSchoolId = incrementer()
const genProgramRequirementId = incrementer()

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
        payment_type: null
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

const makeRequirementRootNode = (
  program: Program,
  includeRequirements: boolean,
  includeElectives: boolean
) => {
  // @param includeElectives: if true, will define "children" under the requirements operator node as an empty array.
  // If false, the "children" variable will be undefined.
  // @param includeRequirements: if true, will define "children" under the electives operator node as an empty array.
  // If false, the "children" variable will be undefined.
  const requirementsChildrenArray = includeRequirements ? [] : undefined
  const electivesChildrenArray = includeElectives ? [] : undefined
  const result = {
    id:   genProgramRequirementId.next().value,
    data: {
      node_type: "program_root",
      program:   program.id
    },
    children: [
      {
        id:   genProgramRequirementId.next().value,
        data: {
          node_type: "operator",
          program:   program.id,
          operator:  "all_of",
          title:     "Required Courses"
        },
        children: requirementsChildrenArray
      },
      {
        id:   genProgramRequirementId.next().value,
        data: {
          node_type:      "operator",
          program:        program.id,
          operator:       "min_number_of",
          operator_value: 1,
          title:          "Elective Courses"
        },
        children: electivesChildrenArray
      }
    ]
  }
  return result
}

const makeDEDPSampleRequirementsTree = (
  program: Program,
  courses: Array<LearnerRecordCourse | CourseDetail>,
  shouldBeCompleted: boolean,
  includeElectives: boolean,
  includeRequirements: boolean
) => {
  // Makes a requirements tree that looks like it did for DEDP in RC for 3T2022.
  // You need to pass in an array of 7 courses.

  // @param includeElectives: if true, will associate some of the courses to the elective node's children.
  // @param includeRequirements: if true, will associate some of the courses to the required node's children.

  // make root node
  // root nodes have two children - both operators, one for reqs and one for electives
  const rn = makeRequirementRootNode(
    program,
    includeRequirements,
    includeElectives
  )

  // add courses to the Required Courses node
  if (rn.children[0].children) {
    for (let i = 0; i < 3; i++) {
      rn.children[0].children.push(
        makeRequirementCourseNode(courses[i], rn.children[0], shouldBeCompleted)
      )
    }
  }

  // add base-level electives
  if (rn.children[1].children) {
    for (let i = 3; i < 5; i++) {
      rn.children[1].children.push(
        makeRequirementCourseNode(courses[i], rn.children[1], shouldBeCompleted)
      )
    }

    // add nested operator and electives
    const nestedElectiveOp = {
      id:   genProgramRequirementId.next().value,
      data: {
        node_type:      "operator",
        program:        program.id,
        operator:       "min_number_of",
        operator_value: 1,
        title:          "One of"
      },
      children: []
    }

    for (let i = 5; i < courses.length; i++) {
      nestedElectiveOp.children.push(
        makeRequirementCourseNode(
          courses[i],
          nestedElectiveOp,
          shouldBeCompleted
        )
      )
    }
    if (rn.children[1].children) {
      rn.children[1].children.push(nestedElectiveOp)
    }
  }

  return rn
}

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

export const makeProgramWithReqTree = (): Program => {
  const program = makeProgram()

  // for the reqtree stuff to work, the program needs 6 more courses
  for (let i = 0; i < 6; i++) {
    program.courses.push(makeCourseDetailWithRuns())
  }

  program.req_tree = [
    makeDEDPSampleRequirementsTree(program, program.courses, false, true, true)
  ]

  return program
}

export const makeProgramWithOnlyRequirements = (): Program => {
  const program = makeProgram()

  // for the reqtree stuff to work, the program needs 6 more courses
  for (let i = 0; i < 6; i++) {
    program.courses.push(makeCourseDetailWithRuns())
  }

  program.req_tree = [
    makeDEDPSampleRequirementsTree(program, program.courses, false, false, true)
  ]

  return program
}

export const makeProgramWithOnlyElectives = (): Program => {
  const program = makeProgram()

  // for the reqtree stuff to work, the program needs 6 more courses
  for (let i = 0; i < 6; i++) {
    program.courses.push(makeCourseDetailWithRuns())
  }

  program.req_tree = [
    makeDEDPSampleRequirementsTree(program, program.courses, false, true, false)
  ]

  return program
}

export const makeProgramWithNoElectivesOrRequirements = (): Program => {
  const program = makeProgram()

  // for the reqtree stuff to work, the program needs 6 more courses
  for (let i = 0; i < 6; i++) {
    program.courses.push(makeCourseDetailWithRuns())
  }

  program.req_tree = [
    makeDEDPSampleRequirementsTree(
      program,
      program.courses,
      false,
      false,
      false
    )
  ]

  return program
}

export const makeCertificate = (): Certificate => ({
  link: `/certificate/program/${casual.uuid}`,
  uuid: casual.uuid
})

export const makeProgramEnrollment = (
  cert: boolean = false
): ProgramEnrollment => ({
  program:     makeProgram(),
  enrollments: makeCourseRunEnrollment(),
  certificate: cert ? makeCertificate() : undefined
})

export const makeLearnerRecordCertificate = (): LearnerRecordCertificate => ({
  uuid: casual.uuid,
  link: casual.array_of_words(3).join("/")
})

export const makeLearnerRecordGrade = (): LearnerRecordGrade => ({
  grade:         Math.ceil(Math.random() * 100) / 100,
  letter_grade:  String.fromCharCode(casual.integer(0, 3) + 65),
  passed:        casual.coin_flip,
  set_by_admin:  casual.coin_flip,
  grade_percent: Math.ceil(Math.random() * 100)
})

export const makeLearnerRecordCourse = (): LearnerRecordCourse => ({
  title:       casual.short_description,
  id:          genCourseId.next().value,
  readable_id: casual.word.concat(genCoursewareId.next().value),
  reqtype:     null,
  grade:       casual.coin_flip ? makeLearnerRecordGrade() : null,
  certificate: casual.coin_flip ? makeLearnerRecordCertificate() : null
})

export const makeLearnerRecordProgram = (): LearnerRecordProgram => ({
  title:        casual.short_description,
  readable_id:  casual.word.concat(genCoursewareId.next().value),
  courses:      [],
  requirements: []
})

export const makePartnerSchool = (): PartnerSchool => ({
  id:    genPartnerSchoolId.next().value,
  name:  casual.company_name,
  email: casual.email
})

export const makeLearnerRecordShare = (
  forPartnerSchool: boolean
): LearnerRecordShare => ({
  share_uuid:     casual.uuid,
  created_on:     casual.date(),
  updated_on:     casual.date(),
  is_active:      casual.coin_flip,
  user:           casual.integer(0, 1000),
  program:        casual.integer(0, 1000),
  partner_school: forPartnerSchool ? casual.integer(0, 1000) : null
})

export const makeLearnerRecordUser = (): LearnerRecordUser => ({
  name:     casual.name,
  email:    casual.email,
  username: casual.username
})

export const makeRequirementCourseNode = (
  course: LearnerRecordCourse | CourseDetail,
  parentNode: ProgramRequirement,
  shouldBeCompleted: boolean
): ProgramRequirement => {
  const courseNode = {
    id:   genProgramRequirementId.next().value,
    data: {
      node_type: "course",
      program:   parentNode.data.program,
      course:    course.id
    },
    children: []
  }

  if (Object.getOwnPropertyNames(course).includes("grade")) {
    if (shouldBeCompleted || casual.coin_flip) {
      course.grade = makeLearnerRecordGrade()
      course.certificate = makeLearnerRecordCertificate()
    }

    course.reqtype = parentNode.data.title
  }

  return courseNode
}

export const makeLearnerRecord = (
  shouldBeCompleted: boolean
): LearnerRecord => {
  // This does a lot of things. It will generate a program with a handful of
  // courses, some of which are required and some are electives, with the
  // requisite requirements tree, and will generate grades for your fake learner
  // depending on the flag.

  const partnerSchools = []
  const courses = []

  for (let i = 0; i < 5; i++) {
    partnerSchools.push(makePartnerSchool())
  }

  // mirroring RC DEDP as of 12/1 - 3 required, two electives and then a nested
  // elective with two more courses in it
  for (let i = 0; i < 7; i++) {
    courses.push(makeLearnerRecordCourse())
  }

  const learnerRecord = {
    user:            makeLearnerRecordUser(),
    program:         makeLearnerRecordProgram(),
    sharing:         [],
    partner_schools: partnerSchools
  }

  learnerRecord.program.requirements = [
    makeDEDPSampleRequirementsTree(
      learnerRecord.program,
      courses,
      shouldBeCompleted,
      true,
      true
    )
  ]
  learnerRecord.program.courses = courses

  return learnerRecord
}
