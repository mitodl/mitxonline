import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"
import ProgramCourseInfoCard from "./ProgramCourseInfoCard"
import { enrollmentHasPassingGrade } from "../lib/courseApi"

import type {
  ProgramEnrollment,
  CourseDetailWithRuns
} from "../flow/courseTypes"

interface ProgramEnrollmentDrawerProps {
  enrollment: ProgramEnrollment | null,
  showDrawer: Function,
  isHidden: boolean,
}

export class ProgramEnrollmentDrawer extends React.Component<ProgramEnrollmentDrawerProps> {
  renderCourseInfoCard(course: CourseDetailWithRuns) {
    const { enrollment } = this.props
    let found = undefined

    for (let i = 0; i < course.courseruns.length; i++) {
      found = enrollment.enrollments.find(
        elem => elem.run.id === course.courseruns[i].id
      )
    }

    if (found === undefined) {
      return (
        <ProgramCourseInfoCard
          key={course.readable_id}
          course={course}
        ></ProgramCourseInfoCard>
      )
    }

    return (
      <EnrolledItemCard
        key={found.readable_id}
        enrollment={found}
        isProgramCard={true}
      ></EnrolledItemCard>
    )
  }

  isRequired(course) {
    const { enrollment } = this.props

    return enrollment.program.requirements.required.indexOf(course.id) >= 0
  }

  isElective(course) {
    const { enrollment } = this.props

    return enrollment.program.requirements.electives.indexOf(course.id) >= 0
  }

  passedCount() {
    const { enrollment } = this.props

    let i = 0
    let passedFlags = 0

    for (i = 0; i < enrollment.enrollments.length; i++) {
      if (enrollmentHasPassingGrade(enrollment.enrollments[i])) {
        passedFlags++
      }
    }

    return passedFlags
  }

  render() {
    const { isHidden, enrollment, showDrawer } = this.props

    const closeDrawer = () => {
      if (isHidden) {
        showDrawer()
      }
    }

    const backgroundClass = isHidden
      ? "drawer-background open"
      : "drawer-background"
    const drawerClass = `nav-drawer ${isHidden ? "open" : "closed"}`

    const passedCourses = enrollment === null ? null : this.passedCount()

    return enrollment === null ? null : (
      <>
        <div className={backgroundClass}>
          <div
            className={drawerClass}
            id="program_enrollment_drawer"
            tabIndex="-1"
            role="dialog"
            aria-modal="true"
            aria-label="program courses"
            aria-describedby="program_enrolled_items"
            aria-hidden={!isHidden ? true : false}
          >
            <div
              className="row chrome d-flex flex-row"
              id="program_enrollment_title"
            >
              <h3 className="flex-grow-1">{enrollment.program.title}</h3>
              <button
                type="button"
                className="close"
                aria-label="Close"
                onClick={closeDrawer}
              >
                <span>&times;</span>
              </button>
            </div>
            <div className="row chrome" id="program_enrollment_subtite">
              <p>
                Program overview: {enrollment.program.courses.length} courses |{" "}
                {passedCourses} passed |{" "}
                {enrollment.program.courses.length -
                  enrollment.enrollments.length}{" "}
                not enrolled
              </p>
            </div>
            <div className="row enrolled-items" id="program_enrolled_items">
              <h6>
                REQUIRED ({enrollment.program.requirements.required.length})
              </h6>

              {enrollment.program.courses.map(courseEnrollment =>
                this.isRequired(courseEnrollment)
                  ? this.renderCourseInfoCard(courseEnrollment)
                  : null
              )}
            </div>
            <div className="row enrolled-items" id="program_unenrolled_items">
              <h6>
                OPTIONAL ({enrollment.program.requirements.electives.length})
              </h6>

              {enrollment.program.courses.map(courseEnrollment => {
                return this.isElective(courseEnrollment)
                  ? this.renderCourseInfoCard(courseEnrollment)
                  : null
              })}
            </div>
          </div>
        </div>
      </>
    )
  }
}
