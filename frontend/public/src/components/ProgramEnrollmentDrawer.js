import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"
import ProgramCourseInfoCard from "./ProgramCourseInfoCard"
import { extractCoursesFromNode } from "../lib/courseApi"
import type {
  ProgramEnrollment,
  CourseDetailWithRuns
} from "../flow/courseTypes"

interface ProgramEnrollmentDrawerProps {
  enrollment: ProgramEnrollment | null,
  showDrawer: Function,
  isHidden: boolean,
  redirectToCourseHomepage: Function,
}

export class ProgramEnrollmentDrawer extends React.Component<ProgramEnrollmentDrawerProps> {
  renderCourseInfoCard(course: CourseDetailWithRuns) {
    const { enrollment } = this.props

    let found = undefined

    if (course.courseruns) {
      for (let i = 0; i < enrollment.enrollments.length; i++) {
        if (
          enrollment.enrollments[i].run.course.readable_id ===
          course.readable_id
        ) {
          found = enrollment.enrollments[i]
        }
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
        key={found.run.course.readable_id}
        enrollment={found}
        isProgramCard={true}
        redirectToCourseHomepage={this.redirectToCourseHomepage}
      ></EnrolledItemCard>
    )
  }

  /*
   * Trap the navigation focus to the modal only.  This improves accessibility by restricting users
   * to tab-navigate between elements in the modal and not the dashboard while the modal is open.
   */
  restrictFocusToDialog() {
    const focusableElements = "button, [href]"
    const modal = document.getElementById("program_enrollment_drawer")
    if (modal) {
      const firstFocusableElement = modal.querySelectorAll(focusableElements)[0] // get first element to be focused inside modal
      const focusableContent = modal.querySelectorAll(focusableElements)
      const lastFocusableElement = focusableContent[focusableContent.length - 1] // get last element to be focused inside modal
      document.addEventListener("keydown", function(e) {
        const isTabPressed = e.key === "Tab" || e.keyCode === 9

        if (!isTabPressed) {
          return
        }

        if (e.shiftKey) {
          // if shift key pressed for shift + tab combination
          if (document.activeElement === firstFocusableElement) {
            lastFocusableElement.focus() // add focus for the last focusable element
            e.preventDefault()
          }
        } else {
          // if tab key is pressed
          if (document.activeElement === lastFocusableElement) {
            // if focused has reached to last focusable element then focus first focusable element after pressing tab
            firstFocusableElement.focus() // add focus for the first focusable element
            e.preventDefault()
          }
        }
      })

      firstFocusableElement.focus()
    }
  }

  renderCourseCards() {
    const { enrollment } = this.props

    return (
      <React.Fragment>
        {enrollment.program.req_tree[0].children.map(node => {
          const interiorCourses = extractCoursesFromNode(node, enrollment)
          const overviewAriaLabel = `${interiorCourses.length} ${node.data.title}`

          return (
            <div
              className="row enrolled-items"
              id={`program_enrolled_node_${node.id}`}
              key={`program_enrolled_node_${node.id}`}
              aria-label={overviewAriaLabel}
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

  /*
   * Returns an array; the first item in the array equals the number of courses
   * in the Program, the second number equals the number of courses in the
   * program for which the user has a passing grade.
   */
  getNumberOfCoursesInProgram() {
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

      return [enrollment.program.courses.length, passed]
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

    return [allEnrollments.length, passedCount]
  }

  renderProgramOverview() {
    const courseNumbers = this.getNumberOfCoursesInProgram()

    return (
      <>
        {courseNumbers[0]} courses | {courseNumbers[1]} passed
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

    if (isHidden) {
      this.restrictFocusToDialog()
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

    const courseNumbers = this.getNumberOfCoursesInProgram()

    return (
      <div className={backgroundClass}>
        <div
          className={drawerClass}
          id="program_enrollment_drawer"
          role="dialog"
          tabIndex="-1"
          aria-modal="true"
          aria-label={enrollment.program.title}
          aria-description={`${courseNumbers[0]} courses, ${courseNumbers[1]} passed`}
        >
          <div
            className="row chrome d-flex flex-row mr-3"
            id="program_enrollment_title"
          >
            <h3 id="dialog-title" className="flex-grow-1">
              {enrollment.program.title}
            </h3>
            <button
              type="button"
              className="close"
              aria-label="Close"
              onClick={closeDrawer}
            >
              <span></span>
            </button>
          </div>
          <div className="row chrome">
            <p>
              Program overview: {this.renderProgramOverview()}
              <br />
              <a
                href={`/records/${enrollment.program.id}/`}
                rel="noreferrer"
                target="_blank"
              >
                View program record
              </a>
            </p>
          </div>
          {enrolledItemCards}
        </div>
      </div>
    )
  }
}
