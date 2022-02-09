import moment from "moment"
import { without } from "ramda"
import React, { useCallback, useState } from "react"
import DocumentTitle from "react-document-title"
import { useSelector } from "react-redux"
import {
  Dropdown,
  DropdownItem,
  DropdownMenu,
  DropdownToggle,
  Tooltip
} from "reactstrap"
import { useMutation, useRequest } from "redux-query-react"
import Loader from "../../components/Loader"
import {
  ALERT_TYPE_DANGER,
  ALERT_TYPE_SUCCESS,
  DASHBOARD_PAGE_TITLE
} from "../../constants"
import { useNotifications } from "../../hooks/notifications"
import useSettings from "../../hooks/settings"
import { useLoggedInUser } from "../../hooks/user"
import {
  isLinkableCourseRun,
  isWithinEnrollmentPeriod
} from "../../lib/courseApi"
import {
  courseEmailsSubscriptionMutation,
  deactivateEnrollmentMutation,
  enrollmentsQuery,
  enrollmentsSelector
} from "../../lib/queries/enrollment"
import { routes } from "../../lib/urls"
import {
  formatPrettyDateTimeAmPmTz,
  isSuccessResponse,
  parseDateString
} from "../../lib/util"
import { RunEnrollment } from "../../types/course"

export default function DashboardPage() {
  /* eslint-disable-next-line camelcase */
  const { site_name, support_email } = useSettings()
  const { addNotification } = useNotifications()
  const [{ isPending }] = useRequest(enrollmentsQuery())
  const enrollments = useSelector<any, RunEnrollment[] | null>(
    enrollmentsSelector
  )
  const [submittingEnrollmentId, setSubmittingEnrollmentId] = useState<
    number | null
  >(null)
  const [activeMenuIds, setActiveMenuIds] = useState<number[]>([])
  const [activeEnrollMsgIds, setActiveEnrollMsgIds] = useState<number[]>([])

  const [, deactivateEnrollment] = useMutation((enrollmentId: number) =>
    deactivateEnrollmentMutation(enrollmentId)
  )

  const [
    ,
    courseEmailsSubscription
  ] = useMutation((enrollmentId: number, emailsSubscription: boolean) =>
    courseEmailsSubscriptionMutation(enrollmentId, emailsSubscription)
  )

  const isActiveMenuId = useCallback(
    (itemId: number): boolean => {
      return !!activeMenuIds.find(id => id === itemId)
    },
    [activeMenuIds]
  )

  const isActiveEnrollMsgId = useCallback(
    (itemId: number): boolean => {
      return !!activeEnrollMsgIds.find(id => id === itemId)
    },
    [activeEnrollMsgIds]
  )

  const toggleActiveMenuId = useCallback(
    (itemId: number) => {
      return () => {
        const isActive = isActiveMenuId(itemId)

        setActiveMenuIds(
          isActive
            ? without([itemId], activeMenuIds)
            : [...activeMenuIds, itemId]
        )
      }
    },
    [isActiveMenuId, activeMenuIds, setActiveMenuIds]
  )

  const toggleActiveEnrollMsgId = useCallback(
    (itemId: number) => {
      return () => {
        const isActive = isActiveEnrollMsgId(itemId)
        setActiveEnrollMsgIds(
          isActive
            ? without([itemId], activeEnrollMsgIds)
            : [...activeEnrollMsgIds, itemId]
        )
      }
    },
    [activeEnrollMsgIds, isActiveEnrollMsgId, setActiveEnrollMsgIds]
  )

  const onDeactivate = useCallback(
    async (enrollment: RunEnrollment) => {
      setSubmittingEnrollmentId(enrollment.id)

      try {
        const resp = await deactivateEnrollment(enrollment.id)

        if (isSuccessResponse(resp)) {
          addNotification("unenroll-status", {
            type:  ALERT_TYPE_SUCCESS,
            props: {
              text: `You have been successfully unenrolled from ${enrollment.run.title}.`
            }
          })
        } else {
          addNotification("unenroll-status", {
            type:  ALERT_TYPE_DANGER,
            props: {
              /* eslint-disable-next-line camelcase */
              text: `Something went wrong with your request to unenroll. Please contact support at ${support_email}.`
            }
          })
        }
        // Scroll to the top of the page to make sure the user sees the message
        window.scrollTo(0, 0)
      } finally {
        setSubmittingEnrollmentId(null)
      }
    },
    [setSubmittingEnrollmentId, addNotification]
  )

  const onChangeEmailSettings = useCallback(
    async (enrollment: RunEnrollment) => {
      setSubmittingEnrollmentId(enrollment.id)
      try {
        const subscribed = !enrollment.edx_emails_subscription
        const resp = await courseEmailsSubscription(enrollment.id, subscribed)

        if (isSuccessResponse(resp)) {
          addNotification("subscription-status", {
            type:  ALERT_TYPE_SUCCESS,
            props: {
              text: `You have been successfully ${
                subscribed ? "subscribed to" : "unsubscribed from"
              } course ${enrollment.run.title} emails.`
            }
          })
        } else {
          addNotification("subscription-status", {
            type:  ALERT_TYPE_DANGER,
            props: {
              text: `Something went wrong with your request to course emails subscription. Please contact support at ${SETTINGS.support_email}.`
            }
          })
        }
        // Scroll to the top of the page to make sure the user sees the message
        window.scrollTo(0, 0)
      } finally {
        setSubmittingEnrollmentId(null)
      }
    },
    [setSubmittingEnrollmentId, addNotification]
  )

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${DASHBOARD_PAGE_TITLE}`}>
      <div className="std-page-body dashboard container">
        <Loader isLoading={isPending}>
          <h1>My Courses</h1>
          <div className="enrolled-items">
            {enrollments && enrollments.length > 0 ? (
              enrollments.map((enrollment: RunEnrollment) => (
                <EnrolledItemCard
                  enrollment={enrollment}
                  isActiveEnrollMsgId={isActiveEnrollMsgId(enrollment.id)}
                  toggleActiveEnrollMsgId={toggleActiveEnrollMsgId}
                  isActiveMenuId={isActiveMenuId(enrollment.id)}
                  toggleActiveMenuId={toggleActiveMenuId}
                  submittingEnrollmentId={submittingEnrollmentId}
                  onChangeEmailSettings={onChangeEmailSettings}
                  onDeactivate={onDeactivate}
                  key={enrollment.run.id}
                />
              ))
            ) : (
              <div className="card no-enrollments p-3 p-md-5 rounded-0">
                <h2>Enroll Now</h2>
                <p>
                  You are not enrolled in any courses yet. Please{" "}
                  <a href={routes.root}>browse our courses</a>.
                </p>
              </div>
            )}
          </div>
        </Loader>
      </div>
    </DocumentTitle>
  )
}

type EnrolledItemCardProps = {
  enrollment: RunEnrollment
  submittingEnrollmentId: number | null
  isActiveMenuId: boolean
  toggleActiveMenuId: (id: number) => void
  isActiveEnrollMsgId: boolean
  toggleActiveEnrollMsgId: (id: number) => void
  onChangeEmailSettings: (enrollment: RunEnrollment) => Promise<void>
  onDeactivate: (enrollment: RunEnrollment) => Promise<void>
}

const EnrolledItemCard = ({
  enrollment,
  submittingEnrollmentId,
  onDeactivate,
  onChangeEmailSettings,
  toggleActiveMenuId,
  isActiveMenuId,
  toggleActiveEnrollMsgId,
  isActiveEnrollMsgId
}: EnrolledItemCardProps) => {
  const currentUser = useLoggedInUser()!

  const unenrollEnabled = isWithinEnrollmentPeriod(enrollment.run)
  const onUnenrollClick = useCallback(() => onDeactivate(enrollment), [
    enrollment
  ])
  const onSubscriptionClick = useCallback(
    () => onChangeEmailSettings(enrollment),
    [enrollment]
  )

  let startDate, startDateDescription

  const title = isLinkableCourseRun(enrollment.run, currentUser) ? (
    <a
      href={enrollment.run.courseware_url!}
      target="_blank"
      rel="noopener noreferrer"
    >
      {enrollment.run.course.title}
    </a>
  ) : (
    enrollment.run.course.title
  )

  if (enrollment.run.start_date) {
    const now = moment()
    startDate = parseDateString(enrollment.run.start_date)!
    const formattedStartDate = formatPrettyDateTimeAmPmTz(startDate)
    startDateDescription = now.isBefore(startDate) ? (
      <span>Starts - {formattedStartDate}</span>
    ) : (
      <span>
        <strong>Active</strong> from {formattedStartDate}
      </span>
    )
  }

  return (
    <div className="enrolled-item container card p-md-3 mb-4 rounded-0">
      <div className="row flex-grow-1">
        {enrollment.run.course.feature_image_src && (
          <div className="col-12 col-md-auto px-0 px-md-3">
            <div className="img-container">
              <img
                src={enrollment.run.course.feature_image_src}
                alt="Preview image"
              />
            </div>
          </div>
        )}
        <div className="col-12 col-md px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between align-content-start flex-nowrap mb-3">
            <h2 className="my-0 mr-3">{title}</h2>
            <Dropdown
              isOpen={isActiveMenuId}
              toggle={toggleActiveMenuId(enrollment.id)}
              id={`enrollmentDropdown-${enrollment.id}`}
            >
              <DropdownToggle className="d-inline-flex unstyled dot-menu">
                <i className="material-icons">more_vert</i>
              </DropdownToggle>
              <DropdownMenu right>
                <span id={`unenrollButtonWrapper-${enrollment.id}`}>
                  <DropdownItem
                    className="unstyled d-block"
                    onClick={onUnenrollClick}
                    {...(!unenrollEnabled ||
                    enrollment.id === submittingEnrollmentId
                      ? {
                        disabled: true
                      }
                      : {})}
                  >
                    Unenroll
                  </DropdownItem>
                </span>
                <span>
                  <DropdownItem
                    className="unstyled d-block"
                    onClick={onSubscriptionClick}
                  >
                    {enrollment.edx_emails_subscription
                      ? "Unsubscribe from emails"
                      : "Subscribe to emails"}
                  </DropdownItem>
                </span>
                {!unenrollEnabled ? (
                  <Tooltip
                    delay={0}
                    placement="bottom-end"
                    container={`enrollmentDropdown-${enrollment.id}`}
                    target={`unenrollButtonWrapper-${enrollment.id}`}
                    className="unenroll-denied-msg"
                    isOpen={isActiveEnrollMsgId}
                    toggle={toggleActiveEnrollMsgId(enrollment.id)}
                  >
                    The enrollment period for this course has ended. If you'd
                    like to unenroll, please contact support.
                  </Tooltip>
                ) : null}
              </DropdownMenu>
            </Dropdown>
          </div>
          <div className="detail">{startDateDescription}</div>
        </div>
      </div>
    </div>
  )
}
