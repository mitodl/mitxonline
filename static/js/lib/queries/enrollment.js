import { pathOr } from "ramda"

import { getCsrfOptions, nextState } from "./util"
import { emptyOrNil } from "../util"

export const enrollmentsSelector = pathOr(null, ["entities", "enrollments"])

export const enrollmentsQueryKey = "enrollments"

export const enrollmentsQuery = () => ({
  queryKey:  enrollmentsQueryKey,
  url:       "/api/enrollments/",
  transform: json => ({
    enrollments: json
  }),
  update: {
    enrollments: nextState
  }
})

export const deactivateEnrollmentMutation = (enrollmentId: number) => ({
  url:     `/api/enrollments/${enrollmentId}/`,
  options: {
    ...getCsrfOptions(),
    method: "DELETE"
  },
  update: {
    enrollments: prevEnrollments => {
      return emptyOrNil(prevEnrollments)
        ? []
        : prevEnrollments.filter(enrollment => enrollment.id !== enrollmentId)
    }
  }
})
