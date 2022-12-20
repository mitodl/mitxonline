import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"
import ProgramCourseInfoCard from "./ProgramCourseInfoCard"
import { extractCoursesFromNode } from "../lib/courseApi"
import { areLearnerRecordsEnabled } from "../lib/util"
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

    if (course.courseruns) {
      for (let i = 0; i < course.courseruns.length; i++) {
        found = enrollment.enrollments.find(
          elem => elem.run.id === course.courseruns[i].id
        )
      }
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

  renderCourseCards() {
    const { enrollment } = this.props

    return (
      <React.Fragment
        key={`drawer-course-list-${enrollment.program.readable_id}`}
      >
        {enrollment.program.req_tree[0].children.map(node => {
          const interiorCourses = extractCoursesFromNode(node, enrollment)

          return (
            <div
              className="row enrolled-items"
              id={`program_enrolled_node_${node.id}`}
              key={`program_enrolled_node_${node.id}`}
            >
              <h6 className="text-uppercase">
                {node.data.title} ({interiorCourses.length})
              </h6>

              {interiorCourses.map(courseEnrollment =>
                this.renderCourseInfoCard(courseEnrollment)
              )}
            </div>
          )
        })}
      </React.Fragment>
    )
  }

  renderFlatCourseCards() {
    const { enrollment } = this.props

    return (
      <div className="row enrolled-items" id="program_enrolled_items">
        <h6>COURSES ({enrollment.program.courses.length})</h6>

        {enrollment.program.courses.map(courseEnrollment =>
          this.renderCourseInfoCard(courseEnrollment)
        )}
      </div>
    )
  }

  renderProgramOverview() {
    const { enrollment } = this.props

    if (enrollment.program.req_tree.length === 0) {
      let passed = 0

      enrollment.enrollments.forEach(elem => {
        passed += elem.grades.reduce(
          (acc, grade) => (grade.passed ? (acc += 1) : acc),
          0
        )
          ? 1
          : 0
      })

      return (
        <>
          {enrollment.program.courses.length} courses | {passed} passed
        </>
      )
    }

    const requiredEnrollments = extractCoursesFromNode(
      enrollment.program.req_tree[0].children[0],
      enrollment
    )
    const electiveEnrollments = extractCoursesFromNode(
      enrollment.program.req_tree[0].children[1],
      enrollment
    )
    const allEnrollments = requiredEnrollments.concat(electiveEnrollments)

    const passedCount = allEnrollments.reduce((acc, indEnrollment) => {
      let passed = 0

      for (let i = 0; i < enrollment.enrollments.length; i++) {
        if (enrollment.enrollments[i].run.course.id === indEnrollment.id) {
          for (let p = 0; p < enrollment.enrollments[i].grades.length; p++) {
            if (enrollment.enrollments[i].grades[p].passed) {
              passed = 1
              break
            }
          }
        }
      }

      return acc + passed
    }, 0)

    return (
      <>
        {allEnrollments.length} courses | {passedCount} passed
      </>
    )
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

    if (enrollment === null) {
      return null
    }

    const enrolledItemCards =
      enrollment.program.requirements.length === 0
        ? this.renderFlatCourseCards()
        : this.renderCourseCards()

    return (
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
              className="row chrome d-flex flex-row mr-3"
              id="program_enrollment_title"
            >
              <h3 className="flex-grow-1">{enrollment.program.title}</h3>
              <button
                type="button"
                className="close"
                aria-label="Close"
                onClick={closeDrawer}
              >
                <span></span>
              </button>
            </div>
            <div className="row chrome" id="program_enrollment_subtite">
              <p>
                Program overview: {this.renderProgramOverview()}
                {areLearnerRecordsEnabled() ? (
                  <>
                    <br />
                    <a
                      href={`/records/${enrollment.program.id}/`}
                      rel="noreferrer"
                      target="_blank"
                    >
                      View program record
                    </a>
                  </>
                ) : null}
              </p>
            </div>
            {enrolledItemCards}
          </div>
        </div>
      </>
    )
  }
}
