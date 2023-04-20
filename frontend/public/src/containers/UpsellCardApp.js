// @flow
import React from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
// $FlowFixMe
import { Badge } from "reactstrap"

import Loader from "../components/Loader"
import GetCertificateButton from "../components/GetCertificateButton"

import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../lib/queries/courseRuns"
import { getFlexiblePriceForProduct, formatLocalePrice } from "../lib/util"

import { isFinancialAssistanceAvailable } from "../lib/courseApi"

import { getCookie } from "../lib/api"
import type { User } from "../flow/authTypes"
import users, { currentUserSelector } from "../lib/queries/users"

type Props = {
  courseId: string,
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  status: ?number,
  upgradeEnrollmentDialogVisibility: boolean,
  addProductToBasket: (user: number, productId: number) => Promise<any>,
  currentUser: User
}
type ProductDetailState = {
  upgradeEnrollmentDialogVisibility: boolean
}

export class UpsellCardApp extends React.Component<Props, ProductDetailState> {
  state = {
    upgradeEnrollmentDialogVisibility: false
  }

  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  renderUpgradeEnrollmentDialog(run: EnrollmentFlaggedCourseRun) {
    const needFinancialAssistanceLink =
      isFinancialAssistanceAvailable(run) &&
      !run.approved_flexible_price_exists ? (
          <p className="text-center financial-assistance-link">
            <a href={run.page.financial_assistance_form_url}>
            Need financial assistance?
            </a>
          </p>
        ) : null
    const product =
      run.products && !run.is_verified && run.is_enrolled && run.is_upgradable
        ? run.products[0]
        : null
    return product ? (
      <div className="card">
        <div className="row d-flex upsell-header">
          <div className="flex-grow-1 align-self-end">
            <Badge color="danger">Enrolled in free course</Badge>
            <h2>Get a certificate</h2>
          </div>
          <div className="text-end align-self-end">
            <h2>{formatLocalePrice(getFlexiblePriceForProduct(product))}</h2>
          </div>
        </div>
        <div className="row">
          <div className="col-12">
            <p>
              You are taking the free version of this course. Upgrade today and,
              upon passing, receive your certificate signed by MIT faculty to
              highlight the knowledge and skills you've gained from this MITx
              course.
            </p>
            <GetCertificateButton productId={product.id} />
            {needFinancialAssistanceLink}
          </div>
        </div>
      </div>
    ) : null
  }
  getEnrollmentForm() {
    const csrfToken = getCookie("csrftoken")
    const { courseRuns } = this.props
    const run = courseRuns ? courseRuns[0] : null
    return (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button type="submit" className="btn enroll-now enroll-now-free">
          No thanks, I'll take the free version
        </button>
      </form>
    )
  }

  render() {
    const { courseRuns, isLoading } = this.props

    const run = courseRuns ? courseRuns[0] : null

    return (
      // $FlowFixMe: isLoading null or undefined
      <Loader isLoading={isLoading}>
        {run ? this.renderUpgradeEnrollmentDialog(run) : null}
      </Loader>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  courseRuns:  courseRunsSelector,
  currentUser: currentUserSelector,
  isLoading:   pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
  status:      pathOr(null, ["queries", courseRunsQueryKey, "status"])
})

const mapPropsToConfig = props => [
  courseRunsQuery(props.courseId),
  users.currentUserQuery()
]

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(UpsellCardApp)
