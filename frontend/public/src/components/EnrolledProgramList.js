// @flow
import React from "react"

import { routes } from "../lib/urls"
import EnrolledItemCard from "./EnrolledItemCard"

import type { ProgramEnrollment, Program } from "../flow/courseTypes"

type EnrolledProgramListProps = {
  enrollments: ProgramEnrollment[],
  toggleDrawer: Function,
  onUnenroll: Function | undefined,
  onUpdateDrawerEnrollment: Function | null
}

export class EnrolledProgramList extends React.Component<EnrolledProgramListProps> {
  renderEnrolledProgramCard(enrollment: Program) {
    const { toggleDrawer, onUnenroll, onUpdateDrawerEnrollment } = this.props

    return (
      <EnrolledItemCard
        key={`program-item-${enrollment.program.id}`}
        enrollment={enrollment}
        toggleProgramDrawer={toggleDrawer}
        onUnenroll={onUnenroll}
        onUpdateDrawerEnrollment={onUpdateDrawerEnrollment}
      ></EnrolledItemCard>
    )
  }

  render() {
    const { enrollments } = this.props

    return enrollments && enrollments.length > 0 ? (
      enrollments.map<ProgramEnrollment>(enrollment =>
        this.renderEnrolledProgramCard(enrollment)
      )
    ) : (
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
