// @flow
import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"

import type { ProgramEnrollment, Program } from "../flow/courseTypes"

type EnrolledProgramListProps = {
  enrollments: ProgramEnrollment[],
  toggleDrawer: Function,
  onUnenroll: Function | null,
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

    return enrollments && enrollments.length > 0
      ? enrollments.map<ProgramEnrollment>(enrollment =>
        this.renderEnrolledProgramCard(enrollment)
      )
      : null
  }
}

export default EnrolledProgramList
