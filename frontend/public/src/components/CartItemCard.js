// @flow
import React from "react"
import type { Product } from "../flow/cartTypes"
import { generateStartDateText } from "../lib/courseApi"

type Props = {
  product: Product
}

export class CartItemCard extends React.Component<Props> {
  courseAboutLink(linkText: string, course: Object) {
    return (
      <a
        href={course.page !== null ? course.page.page_url : "#"}
        target="_blank"
        rel="noopener noreferrer"
      >
        {linkText}
      </a>
    )
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

    const courseDetail = this.courseAboutLink("Course details", course)

    const readableId =
      course !== undefined
        ? purchasableObject.course_number
        : purchasableObject.run_tag

    const startDateDescription = generateStartDateText(purchasableObject)
    const courseImage =
      course !== undefined && course.page !== null ? (
        <img src={course.page.feature_image_src} alt="" />
      ) : null
    const cardKey = `cartsummarycard_${product.id}`

    return (
      <div className="enrolled-item container card" key={cardKey}>
        <div className="row flex-grow-1 enrolled-item-info">
          <div className="col-12 col-md-auto p-0">
            <div className="img-container">{courseImage}</div>
          </div>

          <div className="col-12 col-md enrollment-details-container">
            <h2 className="">{title}</h2>
            <div className="detail">
              {readableId} |{" "}
              {startDateDescription !== null && startDateDescription.active ? (
                <span>
                  <strong className="text-dark">Starts</strong>{" "}
                  {startDateDescription.datestr}
                </span>
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
