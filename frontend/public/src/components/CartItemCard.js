// @flow
import React from "react"
import type { BasketItem, Product } from "../flow/cartTypes"
import moment from "moment"
import { formatPrettyDateTimeAmPmTz, parseDateString } from "../lib/util"
import { generateStartDateText } from "../lib/courseApi"

type Props = {
  product: Product
}

export class CartItemCard extends React.Component<Props> {
  courseAboutLink(linkText, course) {
    return (<a href={course.page !== null ? course.page.page_url : "#"} target="_blank" rel="noopener noreferrer">
      {linkText}
    </a>)
  }

  render() {
    const { product } = this.props
    if (product.purchasable_object === null) {
      return null
    }

    const purchasableObject = product.purchasable_object
    const course = purchasableObject.course

    const title =
      course !== undefined ? (
        this.courseAboutLink(course.title, course)
      ) : (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {product.description}
        </a>
      )

    const courseDetail =
      this.courseAboutLink("Course details", course)

    const readableId =
      course !== undefined
        ? purchasableObject.readable_id.split('+')[1]
        : purchasableObject.run_tag

    const startDateDescription = generateStartDateText(purchasableObject)
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
        <div className="row d-flex flex-md-columm p-md-3">
          <div className="img-container">{courseImage}</div>

          <div className="flex-grow-1 d-md-flex flex-column w-50 mx-3">
            <h5 className="">{title}</h5>
            <div className="detail">
              {readableId}
              <br />
              {startDateDescription !== null && startDateDescription.active ? (
                <span>Starts - {startDateDescription.datestr}</span>
              ) : (
                <span>
                  {startDateDescription === null ? null : (
                    <span>
                      <strong>Active</strong> from{" "}
                      {startDateDescription.datestr}
                    </span>
                  )}
                </span>
              )}
            </div>
            <div className="enrollment-extra-links d-flex">
              {course !== undefined && courseDetail}
            </div>
          </div>
        </div>{" "}
      </div>
    )
  }
}
