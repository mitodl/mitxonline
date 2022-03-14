// @flow
import React from "react"
import type { BasketItem, Product } from "../flow/cartTypes"
import moment from "moment"
import { formatPrettyDateTimeAmPmTz, parseDateString } from "../lib/util"

type Props = {
  product: Product
}

export class CartItemCard extends React.Component<Props> {
  render() {
    const { product } = this.props
    if (product.purchasable_object === null) {
      return null
    }

    const purchasableObject = product.purchasable_object
    const course = purchasableObject.course

    const title =
      course !== undefined ? (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {course.title}
        </a>
      ) : (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {product.description}
        </a>
      )

    const readableId =
      course !== undefined
        ? purchasableObject.readable_id
        : purchasableObject.run_tag

    let startDate = ""
    let startDateDescription = ""

    if (purchasableObject.start_date) {
      const now = moment()
      startDate = parseDateString(purchasableObject.start_date)
      const formattedStartDate = formatPrettyDateTimeAmPmTz(startDate)
      startDateDescription = now.isBefore(startDate) ? (
        <span>Starts - {formattedStartDate}</span>
      ) : (
        <span>
          <strong>Active</strong> from {formattedStartDate}
        </span>
      )
    }

    const courseImage =
      course !== undefined && course.page !== null ? (
        <img src={course.page.feature_image_src} alt={course.title} />
      ) : null
    const cardKey = `cartsummarycard_${product.id}`

    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 flex-grow-1"
        key={cardKey}
      >
        <div className="row d-flex flex-sm-columm p-md-3">
          <div className="img-container">{courseImage}</div>

          <div className="flex-grow-1 d-sm-flex flex-column w-50 mx-3">
            <h5 className="">{title}</h5>
            <div className="detail">
              {readableId}
              <br />
              {startDateDescription !== undefined ? startDateDescription : ""}
            </div>
          </div>
        </div>{" "}
      </div>
    )
  }
}
