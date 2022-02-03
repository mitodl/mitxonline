import { pathOr } from "ramda"
import { RunEnrollment } from "../../types/course"
import { emptyOrNil } from "../util"
import { getCsrfOptions, nextState } from "./util"

export const enrollmentsSelector = pathOr(null, ["entities", "enrollments"])
export const enrollmentsQueryKey = "enrollments"
export const enrollmentsQuery = () => ({
  queryKey:  enrollmentsQueryKey,
  url:       "/api/enrollments/",
  transform: (json: Array<RunEnrollment>) => ({
    enrollments: json
  }),
  update: {
    enrollments: nextState
  }
})
export const deactivateEnrollmentMutation = (enrollmentId: number) => ({
  url:     `/api/enrollments/${enrollmentId}/`,
  options: { ...getCsrfOptions(), method: "DELETE" },
  update:  {
    enrollments: (prevEnrollments: Array<RunEnrollment>) => {
      return emptyOrNil(prevEnrollments)
        ? []
        : prevEnrollments.filter(enrollment => enrollment.id !== enrollmentId)
    }
  }
})

export const courseEmailsSubscriptionMutation = (
  enrollmentId: number,
  emailsSubscription = false
) => ({
  url:  `/api/enrollments/${enrollmentId}/`,
  body: {
    receive_emails: emailsSubscription ? "on" : ""
  },
  options: {
    ...getCsrfOptions(),
    method: "PATCH"
  },
  update: {
    enrollments: (prevEnrollments: Array<RunEnrollment>) => {
      return (prevEnrollments || []).map(enrollment => ({
        ...enrollment,
        edx_emails_subscription:
          enrollment.id === enrollmentId
            ? emailsSubscription
            : enrollment.edx_emails_subscription
      }))
    }
  }
})
