// @flow
import React from "react"
import { checkFeatureFlag } from "../lib/util"

import CourseProductDetailEnroll from "../components/CourseProductDetailEnroll"
import ProgramProductDetailEnroll from "../components/ProgramProductDetailEnroll"

const expandExpandBlock = (event: MouseEvent) => {
  event.preventDefault()
  const blockTarget = event.target
  if (blockTarget instanceof HTMLElement) {
    const block = blockTarget.getAttribute("data-expand-body")
    if (block) {
      const elem = document.querySelector(`div#exp${block}`)
      elem && elem.classList && elem.classList.toggle("open")
      if (elem.classList.contains("open")) {
        event.srcElement.innerText = "Show Less"
      } else {
        event.srcElement.innerText = "Show More"
      }
    }
  }
}

type Props = {
  courseId: ?string,
  programId: ?string
}

export class ProductDetailEnrollApp extends React.Component<Props> {
  render() {
    const { courseId, programId } = this.props

    const showNewDesign = checkFeatureFlag("mitxonline-new-product-page")

    if (showNewDesign) {
      document.querySelectorAll("a.expand_here_link").forEach(link => {
        link.removeEventListener("click", expandExpandBlock)
        link.addEventListener("click", expandExpandBlock)
      })
    }

    return programId && showNewDesign ? (
      <ProgramProductDetailEnroll
        programId={programId}
      ></ProgramProductDetailEnroll>
    ) : (
      <CourseProductDetailEnroll
        courseId={courseId}
      ></CourseProductDetailEnroll>
    )
  }
}

export default ProductDetailEnrollApp
