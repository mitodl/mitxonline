// @flow
import React from "react"

import { routes } from "../lib/urls"
import EnrolledItemCard from "./EnrolledItemCard"

import type { RunEnrollment } from "../flow/courseTypes"

type EnrolledCourseListProps = {
  enrollments: RunEnrollment[],
  redirectToCourseHomepage: Function
}

export class EnrolledCourseList extends React.Component<EnrolledCourseListProps> {
  renderEnrolledItemCard(enrollment: RunEnrollment) {
    const { redirectToCourseHomepage } = this.props

    return (
      <EnrolledItemCard
        key={enrollment.id}
        enrollment={enrollment}
        toggleProgramInfo={null}
        redirectToCourseHomepage={redirectToCourseHomepage}
      ></EnrolledItemCard>
    )
  }

  render() {
    const { enrollments } = this.props

    return enrollments && enrollments.length > 0 ? (
      enrollments.map<RunEnrollment>(enrollment =>
        this.renderEnrolledItemCard(enrollment)
      )
    ) : (
      <div className="no-enrollments std-card">
        <div className="std-card-body">
          <h2>Enroll Now</h2>
          <p>
            You are not enrolled in any courses yet. Please{" "}
            <a className="fw-bold" href={routes.catalog}>
              browse our courses
            </a>
            .
          </p>
        </div>
      </div>
    )
  }
}

export default EnrolledCourseList
