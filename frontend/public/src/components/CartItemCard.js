// @flow
import React from "react"
import type { Product } from "../flow/cartTypes"
import { courseRunStatusMessage } from "../lib/courseApi"

type Props = {
  product: Product
}

export class CartItemCard extends React.Component<Props> {
  renderLink(linkText: string, pageUrl: ?string) {
    return (
      <a href={pageUrl || "#"} target="_blank" rel="noopener noreferrer">
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
    const isProgram =
      course === undefined && purchasableObject.readable_id !== undefined

    let title, abbreviation, image, detailLink, statusMessage

    if (course !== undefined) {
      // CourseRun product
      const pageUrl = course.page !== null ? course.page.page_url : null
      title = this.renderLink(course.title, pageUrl)
      abbreviation = purchasableObject.course_number
      image =
        course.page !== null ? (
          <img src={course.page.feature_image_src} alt="" />
        ) : null
      detailLink = this.renderLink("Course details", pageUrl)
      statusMessage = courseRunStatusMessage(purchasableObject)
    } else if (isProgram) {
      // Program product
      const pageUrl =
        purchasableObject.page !== null && purchasableObject.page !== undefined ?
          purchasableObject.page.page_url :
          null
      title = this.renderLink(purchasableObject.title, pageUrl)
      abbreviation = null
      image =
        purchasableObject.page !== null &&
        purchasableObject.page !== undefined ? (
            <img src={purchasableObject.page.feature_image_src} alt="" />
          ) : null
      detailLink = this.renderLink("Program details", pageUrl)
      statusMessage = null
    } else {
      // Fallback (e.g., ProgramRun)
      title = (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {product.description}
        </a>
      )
      abbreviation = purchasableObject.run_tag
      image = null
      detailLink = null
      statusMessage = null
    }

    const cardKey = `cartsummarycard_${product.id}`

    return (
      <div className="enrolled-item container card" key={cardKey}>
        <div className="row flex-grow-1 enrolled-item-info">
          <div className="col-12 col-md-auto p-0">
            <div className="img-container">{image}</div>
          </div>

          <div className="col-12 col-md">
            <h2 className="">{title}</h2>
            <div className="detail">
              {abbreviation}
              {statusMessage}
            </div>
            <div className="enrollment-extra-links d-flex">{detailLink}</div>
          </div>
        </div>{" "}
      </div>
    )
  }
}
