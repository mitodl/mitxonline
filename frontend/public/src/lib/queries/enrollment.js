import { pathOr } from "ramda"

import { getCsrfOptions, nextState } from "./util"
import { emptyOrNil } from "../util"

export const enrollmentsSelector = pathOr(null, ["entities", "enrollments"])
export const enrollmentSelector = pathOr(null, ["entities", "enrollment"])
export const programEnrollmentsSelector = pathOr(null, [
  "entities",
  "program_enrollments"
])
export const learnerRecordSelector = pathOr(null, [
  "entities",
  "learner_record"
])

export const enrollmentsQueryKey = "enrollments"
export const enrollmentQueryKey = "enrollment"
export const programEnrollmentsQueryKey = "program_enrollments"
export const learnerRecordQueryKey = "learner_record"

export const enrollmentsQuery = () => ({
  queryKey:  enrollmentsQueryKey,
  url:       "/api/v1/enrollments/",
  transform: json => ({
    enrollments: json
  }),
  update: {
    enrollments: nextState
  }
})

export const programEnrollmentsQuery = () => ({
  queryKey:  programEnrollmentsQueryKey,
  url:       "/api/v1/program_enrollments/",
  transform: json => ({
    program_enrollments: json
  }),
  update: {
    program_enrollments: nextState
  }
})

export const enrollmentQuery = () => ({
  queryKey:  enrollmentQuery,
  url:       "/api/v1/enrollments/${enrollmentId}",
  transform: json => ({
    enrollment: json
  }),
  update: {
    enrollment: nextState
  }
})

export const learnerRecordQuery = (programId: number) => ({
  queryKey:  learnerRecordQueryKey,
  url:       `/api/records/program/${programId}`,
  transform: json => ({
    learnerRecord: json
  }),
  update: {
    learnerRecord: nextState
  }
})

export const sharedLearnerRecordQuery = (uuid: string) => ({
  queryKey:  learnerRecordQueryKey,
  url:       `/api/records/shared/${uuid}`,
  transform: json => ({
    learnerRecord: json
  }),
  update: {
    learnerRecord: nextState
  }
})

export const deactivateEnrollmentMutation = (enrollmentId: number) => ({
  url:     `/api/v1/enrollments/${enrollmentId}/`,
  options: {
    ...getCsrfOptions(),
    method: "DELETE"
  },
  update: {
    enrollments: prevEnrollments => {
      return emptyOrNil(prevEnrollments) ?
        [] :
        prevEnrollments.filter(enrollment => enrollment.id !== enrollmentId)
    },
    program_enrollments: prevProgramEnrollments => {
      return emptyOrNil(prevProgramEnrollments) ?
        [] :
        prevProgramEnrollments.map(programEnrollment => {
          return {
            ...programEnrollment,
            enrollments: programEnrollment.enrollments.filter(
              enrollment => enrollment.id !== enrollmentId
            )
          }
        })
    }
  }
})

export const deactivateProgramEnrollmentMutation = (programId: number) => ({
  url:     `/api/v1/program_enrollments/${programId}/`,
  options: {
    ...getCsrfOptions(),
    method: "DELETE"
  },
  transform: json => ({
    program_enrollments: json
  }),
  update: {
    program_enrollments: nextState
  }
})

export const courseEmailsSubscriptionMutation = (
  enrollmentId: number,
  emailsSubscription: string = ""
) => ({
  url:  `/api/v1/enrollments/${enrollmentId}/`,
  body: {
    receive_emails: emailsSubscription
  },
  options: {
    ...getCsrfOptions(),
    method: "PATCH"
  },
  update: {
    enrollments: prevEnrollments => {
      if (!emptyOrNil(prevEnrollments)) {
        prevEnrollments.find(
          enrollment => enrollment.id === enrollmentId
        ).edx_emails_subscription = emailsSubscription ? true : false
      } else {
        prevEnrollments = []
      }
      return prevEnrollments
    }
  }
})

export const getLearnerRecordSharingLinkMutation = (
  programId: number,
  partnerSchoolId: number | null
) => ({
  url:  `/api/records/program/${programId}/share/`,
  body: {
    partnerSchool: partnerSchoolId
  },
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  transform: json => ({
    learnerRecord: json
  }),
  update: {
    learnerRecord: nextState
  }
})

export const revokeLearnerRecordSharingLinkMutation = (programId: number) => ({
  url:     `/api/records/program/${programId}/revoke/`,
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  transform: json => ({
    learnerRecord: json
  }),
  update: {
    learnerRecord: nextState
  }
})

export const enrollmentMutation = (runId: number) => ({
  url:  `/enrollments/`,
  body: {
    run:   `${runId}`,
    isapi: true
  },
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  update: {}
})
