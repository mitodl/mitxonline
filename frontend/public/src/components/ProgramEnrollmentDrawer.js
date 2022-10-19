import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"
import ProgramCourseInfoCard from "./ProgramCourseInfoCard"

import type { ProgramEnrollment, CourseDetailWithRuns } from "../flow/courseTypes"

interface ProgramEnrollmentDrawerProps {
  enrollment:  ProgramEnrollment|null,
  showDrawer:   Function,
  isHidden:     boolean,
}

export class ProgramEnrollmentDrawer extends React.Component<ProgramEnrollmentDrawerProps> {
  renderCourseInfoCard(course: CourseDetailWithRuns) {
    const { enrollment } = this.props
    let found = undefined

    console.log(`course is ${course.title} - ${course.readable_id}`)

    for (let i = 0; i < course.courseruns.length; i++) {
      found = enrollment.enrollments.find(elem => elem.run.id === course.courseruns[i].id)
    }

    if (found === undefined) {
      return (<ProgramCourseInfoCard course={course}></ProgramCourseInfoCard>)
    }

    return null
  }

  render() {
    const {
      isHidden,
      enrollment,
      showDrawer,
    } = this.props

    const closeDrawer = () => {
      if (isHidden) {
        showDrawer()
      }
    }

    const backgroundClass = isHidden ? 'drawer-background open' : 'drawer-background'
    const drawerClass = `nav-drawer ${isHidden ? "open" : "closed"}`

    return enrollment === null ? null : (
      <>
        <div className={backgroundClass}>
          <div className={drawerClass} id="program_enrollment_drawer" tabIndex="-1" role="dialog" aria-modal="true" aria-label="program courses" aria-describedby="program_enrolled_items" aria-hidden={!isHidden ? true : false}>
            <div className="row chrome d-flex flex-row" id="program_enrollment_title">
              <h3 className="flex-grow-1">{enrollment.program.title}</h3>
              <button type="button" className="close" aria-label="Close" onClick={closeDrawer}>
                <span>
                  &times;
                </span>
              </button>
            </div>
            <div className="row chrome" id="program_enrollment_subtite">
              <h5>{enrollment.program.courses.length} courses | {enrollment.enrollments.length} enrolled</h5>
            </div>
            <div className="row enrolled-items" id="program_enrolled_items">
              <h5>ENROLLED ({enrollment.enrollments.length})</h5>
              {enrollment.enrollments.length > 0 ? (enrollment.enrollments.map(enrollment => (
                <EnrolledItemCard
                  key={enrollment.id}
                  enrollment={enrollment}>
                </EnrolledItemCard>
              ))) : null}
            </div>
            {enrollment.program.courses.length - enrollment.enrollments.length > 0 ? (
              <div className="row enrolled-items" id="program_unenrolled_items">
                <h5>AVAILABLE ({enrollment.program.courses.length - enrollment.enrollments.length})</h5>

                {enrollment.program.courses.map(course => this.renderCourseInfoCard(course))}
              </div>) : null}
          </div>
        </div>
      </>
    )
  }
}
