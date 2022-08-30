import React from "react"
import { Badge } from "reactstrap"

type Props = {
  enrollmentMode: string
}

export class EnrollmentRoleTag extends React.Component<Props> {
  render() {
    const { enrollmentMode } = this.props

    let label = <Badge color="red">Enrolled in free course</Badge>

    if (enrollmentMode === "verified") {
      label = <Badge color="green">Enrolled in certificate course</Badge>
    }

    return label
  }
}