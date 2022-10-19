// @flow
import React from "react"

import { routes } from "../lib/urls"
import EnrolledItemCard from "./EnrolledItemCard"

import type { RunEnrollment } from "../flow/courseTypes"

type EnrolledCourseListProps = {
    enrollments: RunEnrollment[],
}

export class EnrolledCourseList extends React.Component<EnrolledCourseListProps> {
  renderEnrolledItemCard(enrollment: RunEnrollment) {
    return (
      <EnrolledItemCard
        key={enrollment.id}
        enrollment={enrollment}
        toggleProgramInfo={null}
      ></EnrolledItemCard>
    )
  }

  render() {
    const {
      enrollments,
    } = this.props

    return enrollments && enrollments.length > 0 ?
      enrollments.map<RunEnrollment>(enrollment => this.renderEnrolledItemCard(enrollment))
      : (
        <div className="card no-enrollments p-3 p-md-5 rounded-0">
          <h2>Enroll Now</h2>
          <p>
                You are not enrolled in any courses yet. Please{" "}
            <a href={routes.root}>browse our courses</a>.
          </p>
        </div>
      )
  }
}

export default EnrolledCourseList
