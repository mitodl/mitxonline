// @flow
import React from "react"

import { routes } from "../lib/urls"
import EnrolledItemCard from "./EnrolledItemCard"

import type { ProgramEnrollment, Program } from "../flow/courseTypes"

type EnrolledProgramListProps = {
    enrollments: ProgramEnrollment[],
    toggleDrawer: Function,
}

export class EnrolledProgramList extends React.Component<EnrolledProgramListProps> {
  renderEnrolledProgramCard(enrollment: Program) {
    const { toggleDrawer } = this.props

    return (
      <EnrolledItemCard
        key={enrollment.id}
        enrollment={enrollment}
        toggleProgramDrawer={toggleDrawer}
      ></EnrolledItemCard>
    )
  }

  render() {
    const {
      enrollments,
    } = this.props

    return enrollments && enrollments.length > 0 ?
      enrollments.map<ProgramEnrollment>(enrollment => enrollment.enrollments.length > 0 ? this.renderEnrolledProgramCard(enrollment) : null)
      : (
        <div className="card no-enrollments p-3 p-md-5 rounded-0">
          <h2>Enroll Now</h2>
          <p>
                You are not enrolled in any programs yet. Please{" "}
            <a href={routes.root}>browse our programs</a>.
          </p>
        </div>
      )
  }
}

export default EnrolledProgramList
