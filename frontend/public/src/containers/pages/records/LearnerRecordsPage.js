// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { RECORDS_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync } from "redux-query"
import { pathOr } from "ramda"
import { Button, Modal, ModalHeader, ModalBody } from "reactstrap"
import { Formik, Form, Field } from "formik"
import { isSuccessResponse } from "../../../lib/util"

import { learnerProgramIsCompleted } from "../../../lib/courseApi"

import {
  learnerRecordQuery,
  sharedLearnerRecordQuery,
  learnerRecordQueryKey,
  getLearnerRecordSharingLinkMutation,
  revokeLearnerRecordSharingLinkMutation
} from "../../../lib/queries/enrollment"

import Loader from "../../../components/Loader"

import { addUserNotification } from "../../../actions"
import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../../../constants"

import type { RouterHistory } from "react-router"
import type {
  LearnerRecord,
  LearnerRecordCourse
} from "../../../flow/courseTypes"

import type { CurrentUser } from "../../../flow/authTypes"

type Props = {
  learnerRecord: LearnerRecord,
  isSharedRecord: boolean,
  history: RouterHistory,
  isLoading: boolean,
  addUserNotification: Function,
  forceRequest: Function,
  enableRecordSharing: (
    programId: number,
    partnerSchoolId: number | null
  ) => Promise<any>,
  revokeRecordSharing: (programId: number) => Promise<any>,
  match: any,
  currentUser: CurrentUser
}

type State = {
  toggleRecordSharing: boolean,
  sharingDialogVisibility: boolean,
  partnerSchoolDialogVisibility: boolean,
  linkCopied: boolean,
  isRevoking: boolean,
  isEnablingSharing: boolean
}

export class LearnerRecordsPage extends React.Component<Props, State> {
  state = {
    toggleRecordSharing:           false,
    sharingDialogVisibility:       false,
    partnerSchoolDialogVisibility: false,
    linkCopied:                    false,
    isRevoking:                    false,
    isEnablingSharing:             false
  }

  getProgramId() {
    return this.props.match.params.program.length !== 36
      ? this.props.match.params.program
      : false
  }

  getOnlyProgramId() {
    return parseInt(this.props.match.params.program.length)
  }

  // Renders program's courses table.
  renderCourseTableRow(course: LearnerRecordCourse) {
    return (
      <tr key={`learner-record-course-${course.id}`}>
        <td className="d-flex">
          <span className="flex-grow-1">{course.title}</span>
          <span className="learner-record-req-badges pr-2">
            {course.reqtype === "Required Courses" ? (
              <span className="badge badge-danger">Core</span>
            ) : null}
            {course.reqtype === "Elective Courses" ? (
              <span className="badge badge-success">Elective</span>
            ) : null}
          </span>
        </td>
        <td>{course.readable_id.split("+")[1] || course.readable_id}</td>
        <td>{course.grade ? course.grade.grade_percent : ""}</td>
        <td>{course.grade ? course.grade.letter_grade : ""}</td>
        <td className="learner-record-cert-status">
          {course.certificate ? (
            <span className="badge badge-success">Certificate Earned</span>
          ) : (
            <span className="badge badge-secondary">Not Earned</span>
          )}
        </td>
      </tr>
    )
  }

  // Renders program's courses list items.
  renderCourseListItem(course: LearnerRecordCourse) {
    return (
      <div
        key={`learner-record-course-${course.id}`}
        className="list-group-item d-flex flex-column justify-content-between align-items-start"
      >
        <div className="d-flex w-100 justify-content-between">
          <h5 className="mb-1">{course.title}</h5>
          <span className="learner-record-req-badges pl-2">
            {course.reqtype === "Required Courses" ? (
              <span className="badge badge-danger">Core</span>
            ) : null}
            {course.reqtype === "Elective Courses" ? (
              <span className="badge badge-success">Elective</span>
            ) : null}
          </span>
        </div>
        {course.readable_id.split("+")[1] || course.readable_id}
        {course.grade ? (
          <p className="mb-1">Grade: {course.grade.grade_percent}</p>
        ) : (
          ""
        )}
        {course.certificate ? (
          <span className="badge badge-success">Certificate Earned</span>
        ) : (
          <span className="badge badge-secondary">Not Earned</span>
        )}
      </div>
    )
  }

  renderLearnerInfo() {
    const { learnerRecord } = this.props
    // Only display the leaner info if the current user is different from the leanerRecord's user
    // or the visitor is not logged in.
    return learnerRecord &&
      learnerRecord.user &&
      (!this.props.currentUser.is_authenticated ||
        this.props.currentUser.username !== learnerRecord.user.username) ? (
        <div className="row">
          <div className="col-12 learner-record-user-profile">
            <span className="learner-record-user-name">
              {learnerRecord.user.name}
            </span>
            <br />
            {learnerRecord.user.username} | {learnerRecord.user.email}
          </div>
        </div>
      ) : null
  }

  renderSharingLinkDialog(learnerRecord: LearnerRecord) {
    const { sharingDialogVisibility, linkCopied } = this.state

    const anonymousShare = learnerRecord.sharing.find(
      elem => elem.partner_school === null
    )

    if (anonymousShare === undefined) {
      return null
    }

    const sharingLink = `${window.location.origin}/records/shared/${anonymousShare.share_uuid}/`

    return (
      <Modal
        key="sharing-link-dialog"
        id="sharing-link-modal"
        className="text-center"
        isOpen={sharingDialogVisibility}
        toggle={() => this.toggleSharingLinkDialog()}
      >
        <ModalHeader toggle={() => this.toggleSharingLinkDialog()}>
          Share Link to Record
        </ModalHeader>
        <ModalBody>
          <p>
            Copy this link to share with a university, employer, or anyone else
            of your choosing. Anyone you share this link with will have access
            to your record.
          </p>

          <div className="form-group">
            <input
              type="text"
              readOnly={true}
              className="form-control"
              name="shareLink"
              id="anonymous-sharing-link"
              value={sharingLink}
            />
          </div>

          <div className="mt-2">
            <Button color="primary" onClick={() => this.onCopyLink()}>
              Copy Link{linkCopied ? <span> - Copied!</span> : null}
            </Button>
          </div>
        </ModalBody>
      </Modal>
    )
  }

  renderPartnerSchoolSharingDialog(learnerRecord: LearnerRecord) {
    const { partnerSchoolDialogVisibility } = this.state

    return (
      <Modal
        key="partner-school-modal"
        id="partner-school-modal"
        className="text-center"
        isOpen={partnerSchoolDialogVisibility}
        toggle={() => this.togglePartnerSchoolSharingDialog()}
      >
        <ModalHeader toggle={() => this.togglePartnerSchoolSharingDialog()}>
          Partner School Sharing for {learnerRecord.program.title}
        </ModalHeader>
        <ModalBody>
          <p>
            You can directly share your program record with partners that accept
            credit for this MITx Online program. Once you send the record, you
            cannot unsend it.
          </p>

          <p>Select organization(s) you wish to send this record to:</p>

          <Formik
            onSubmit={this.onSubmitPartnerSchoolShare.bind(this)}
            initialValues={{
              partnerSchool: ""
            }}
            render={() => (
              <Form className="text-center">
                <section>
                  <label htmlFor="partnerSchool" className="text-left">
                    Select School
                  </label>
                  <Field
                    name="partnerSchool"
                    render={({ field }) => (
                      <select
                        {...field}
                        name="partnerSchool"
                        className="form-control"
                      >
                        <option>Choose one...</option>
                        {learnerRecord.partner_schools.map(elem => (
                          <option
                            key={`partner-school-${elem.id}`}
                            value={elem.id}
                          >
                            {elem.name}
                          </option>
                        ))}
                      </select>
                    )}
                  />
                </section>
                <div className="mt-2">
                  <Button type="submit" color="primary">
                    Send Record
                  </Button>{" "}
                  <Button
                    onClick={() => this.togglePartnerSchoolSharingDialog()}
                  >
                    Cancel
                  </Button>
                </div>
              </Form>
            )}
          />

          <div className="form-group"></div>
        </ModalBody>
      </Modal>
    )
  }

  toggleSharingLinkDialog() {
    const { sharingDialogVisibility } = this.state

    this.setState({ sharingDialogVisibility: !sharingDialogVisibility })
  }

  togglePartnerSchoolSharingDialog() {
    const { partnerSchoolDialogVisibility } = this.state
    this.setState({
      partnerSchoolDialogVisibility: !partnerSchoolDialogVisibility
    })
  }

  async onEnableRecordSharing() {
    const { enableRecordSharing, addUserNotification } = this.props

    this.setState({ isEnablingSharing: true })

    const programId = this.getProgramId()

    if (programId === null) {
      return
    }

    const sharingResponse = await enableRecordSharing(
      this.getOnlyProgramId(),
      null
    )

    this.setState({ isEnablingSharing: false })

    if (isSuccessResponse(sharingResponse)) {
      this.setState({
        toggleRecordSharing: true
      })
    } else {
      addUserNotification({
        "share-record-status": {
          type:  ALERT_TYPE_DANGER,
          props: {
            text: `Something went wrong with your request to share your learner record. Please contact support at ${SETTINGS.support_email}.`
          }
        }
      })
    }
  }

  async onSubmitPartnerSchoolShare(values: any) {
    const { enableRecordSharing, addUserNotification } = this.props

    this.setState({ isEnablingSharing: true })

    const programId = this.getProgramId()

    if (programId === null) {
      return
    }

    const sharingResponse = await enableRecordSharing(
      this.getOnlyProgramId(),
      values.partnerSchool
    )

    this.setState({
      isEnablingSharing:             false,
      partnerSchoolDialogVisibility: false
    })

    if (isSuccessResponse(sharingResponse)) {
      this.setState({
        toggleRecordSharing: true
      })

      const partnerSchool = sharingResponse.body.partner_schools.find(
        elem => elem.id === parseInt(values.partnerSchool)
      )

      if (!partnerSchool) {
        addUserNotification({
          "share-record-status": {
            type:  ALERT_TYPE_DANGER,
            props: {
              text: `Something went wrong with your request to share your learner record. Please contact support at ${SETTINGS.support_email}.`
            }
          }
        })
      }

      addUserNotification({
        "share-record-status": {
          type:  ALERT_TYPE_SUCCESS,
          props: {
            text: `Your learner record was sent successfully to ${partnerSchool.name}.`
          }
        }
      })
    } else {
      addUserNotification({
        "share-record-status": {
          type:  ALERT_TYPE_DANGER,
          props: {
            text: `Something went wrong with your request to share your learner record. Please contact support at ${SETTINGS.support_email}.`
          }
        }
      })
    }
  }

  async onRevokeSharing() {
    const { revokeRecordSharing, addUserNotification } = this.props

    this.setState({ isRevoking: true })

    const programId = this.getProgramId()

    if (programId === null) {
      return
    }

    const sharingResponse = await revokeRecordSharing(this.getOnlyProgramId())

    this.setState({ isRevoking: false })

    if (isSuccessResponse(sharingResponse)) {
      this.setState({
        toggleRecordSharing: false
      })

      addUserNotification({
        "subscription-status": {
          type:  ALERT_TYPE_SUCCESS,
          props: {
            text: "Record sharing successfully revoked."
          }
        }
      })
    } else {
      addUserNotification({
        "subscription-status": {
          type:  ALERT_TYPE_DANGER,
          props: {
            text: `Something went wrong with your request to revoke record sharing. Please contact support at ${SETTINGS.support_email}.`
          }
        }
      })
    }
  }

  onCopyLink() {
    const sharebox = document.getElementById("anonymous-sharing-link")

    if (sharebox === null || !(sharebox instanceof HTMLInputElement)) {
      return
    }

    sharebox.select()
    document.execCommand("copy")

    this.setState({ linkCopied: true })
    setTimeout(() => this.setState({ linkCopied: false }), 1500)
  }

  isProgramCompleted() {
    const { learnerRecord } = this.props
    return learnerRecord ? learnerProgramIsCompleted(learnerRecord) : false
  }

  hasSharingEnabled(learnerRecord: LearnerRecord) {
    if (!learnerRecord) {
      return false
    }

    return (
      learnerRecord.sharing.find(elem => elem.partner_school === null) !==
      undefined
    )
  }

  // Render the course record table differently based on screen size.
  renderLearnerRecordTable(learnerRecord: LearnerRecord) {
    return (
      <div>
        {/* Display for mobile screens. */}
        <div className="d-md-none">
          <div className="learner-record">
            <div className="m-0 d-flex flex-column">
              <div>
                <h3 className="learner-record-program-title">
                  {learnerRecord
                    ? learnerRecord.program.title
                    : "MITx Online Program Record"}
                </h3>
                <p>Program Record</p>
              </div>
              <div>
                {!this.isProgramCompleted() ? (
                  <span className="badge badge-learner-completion badge-partially-completed">
                    Partially Completed
                  </span>
                ) : null}
                {this.isProgramCompleted() ? (
                  <span className="badge badge-learner-completion badge-completed">
                    Completed
                  </span>
                ) : null}
              </div>
            </div>

            {this.renderLearnerInfo()}
            <hr />
            <h4>Courses</h4>
            <div className="mt-2 d-flex justify-content-between">
              <div className="list-group">
                {learnerRecord
                  ? learnerRecord.program.courses.map(this.renderCourseListItem)
                  : null}
              </div>
            </div>
          </div>
        </div>

        {/* {Display for desktop screens.} */}
        <div className="d-none d-md-block">
          <div className="learner-record">
            <div className="flex-column">
              <div>
                <div
                  className="d-flex justify-content-between"
                  id="learner-record-school-name"
                >
                  <p className="w-50">MITx Online Program Record</p>
                  <img
                    src="/static/images/mitx-online-logo.png"
                    alt="MITx Online Logo"
                  />
                </div>
              </div>
              <h1 className="flex-grow-1 learner-record-program-title w-50">
                {learnerRecord ? learnerRecord.program.title : null}
              </h1>
              <div>
                {!this.isProgramCompleted() ? (
                  <span className="badge badge-learner-completion badge-partially-completed">
                    Partially Completed
                  </span>
                ) : null}
                {this.isProgramCompleted() ? (
                  <span className="badge badge-learner-completion badge-completed">
                    Completed
                  </span>
                ) : null}
              </div>
            </div>

            {this.renderLearnerInfo()}

            <div className="row">
              <div className="col-12 d-flex justify-content-between">
                <table className="learner-record-table">
                  <thead>
                    <tr>
                      <th>Course Name</th>
                      <th>Course ID</th>
                      <th>
                        Highest
                        <br />
                        Grade
                        <br />
                        Earned
                      </th>
                      <th>
                        Letter
                        <br />
                        Grade
                      </th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {learnerRecord
                      ? learnerRecord.program.courses.map(
                        this.renderCourseTableRow
                      )
                      : null}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  render() {
    const { learnerRecord, isLoading } = this.props
    const { isRevoking, isEnablingSharing } = this.state

    const isSharedRecord = this.getProgramId() ? true : false
    const hasSharingEnabled = this.hasSharingEnabled(learnerRecord)

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${RECORDS_PAGE_TITLE}`}>
        <Loader isLoading={isLoading}>
          <div className="std-page-body container">
            <div className="d-flex flex-row-reverse mb-4">
              {isSharedRecord ? (
                <div className="d-flex learner-record-sharing-controls mb-2">
                  {!hasSharingEnabled ? (
                    <button
                      key="togglesharing"
                      className="btn btn-primary mdl-button"
                      type="button"
                      onClick={() => this.onEnableRecordSharing()}
                    >
                      {isEnablingSharing ? (
                        <>Please Wait...</>
                      ) : (
                        <>Allow Record Sharing</>
                      )}
                    </button>
                  ) : null}
                  {hasSharingEnabled ? (
                    <>
                      <button
                        key="sendlearnerrecord"
                        className="btn btn-primary"
                        type="button"
                        onClick={() => this.togglePartnerSchoolSharingDialog()}
                      >
                        Send Learner Record
                      </button>
                      <button
                        key="sharingdialog"
                        className="btn btn-primary"
                        type="button"
                        onClick={() => this.toggleSharingLinkDialog()}
                      >
                        Share
                      </button>
                      <button
                        key="revokesharing"
                        className="btn btn-primary"
                        type="button"
                        onClick={() => this.onRevokeSharing()}
                      >
                        {isRevoking ? (
                          <>Revoking Access...</>
                        ) : (
                          <>Revoke Sharing</>
                        )}
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>

            {learnerRecord
              ? this.renderLearnerRecordTable(learnerRecord)
              : null}

            {learnerRecord
              ? this.renderPartnerSchoolSharingDialog(learnerRecord)
              : null}
            {learnerRecord ? this.renderSharingLinkDialog(learnerRecord) : null}
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = state => ({
  isLoading: pathOr(
    true,
    ["queries", learnerRecordQueryKey, "isPending"],
    state
  ),
  learnerRecord: state.entities.learnerRecord,
  currentUser:   state.entities.currentUser
})

const enableRecordSharing = (
  programId: number,
  partnerSchoolId: number | null
) =>
  mutateAsync(getLearnerRecordSharingLinkMutation(programId, partnerSchoolId))

const revokeRecordSharing = (programId: number) =>
  mutateAsync(revokeLearnerRecordSharingLinkMutation(programId))

const mapDispatchToProps = {
  enableRecordSharing,
  revokeRecordSharing,
  addUserNotification
}

const mapPropsToConfig = props => [
  props.match.params.program.length !== 36
    ? learnerRecordQuery(props.match.params.program)
    : sharedLearnerRecordQuery(props.match.params.program)
]

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(LearnerRecordsPage)
